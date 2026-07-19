from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.board import Board, BoardMember, Label
from app.models.list_model import BoardList
from app.models.card import Card, CardMember, Checklist, ChecklistItem, Comment, Activity
from app.services import board_service as svc

router = APIRouter(prefix="/api", tags=["boards"])


class BoardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)


class ListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)


class CardCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    list_id: int


class CardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    list_id: int | None = None
    position: float | None = None


class CardMove(BaseModel):
    list_id: int
    position: float


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)


class ChecklistCreate(BaseModel):
    title: str = "Checklist"


class ChecklistItemCreate(BaseModel):
    text: str = Field(..., min_length=1)


class LabelToggle(BaseModel):
    label_id: int


@router.get("/boards")
def list_boards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    boards = (
        db.query(Board)
        .join(BoardMember, BoardMember.board_id == Board.id)
        .filter(BoardMember.user_id == user.id, Board.is_archived == False)
        .order_by(Board.updated_at.desc())
        .all()
    )
    return [
        {"id": b.id, "name": b.name, "background": b.background, "is_starred": b.is_starred, "workspace_id": b.workspace_id}
        for b in boards
    ]


@router.post("/boards", status_code=201)
def create_board(payload: BoardCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = svc.create_board(db, user, payload.name)
    return {"id": board.id, "name": board.name}


@router.get("/boards/{board_id}")
def get_board(board_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = svc.ensure_board_access(db, board_id, user)
    lists_data = []
    for lst in board.lists:
        if lst.is_archived:
            continue
        cards = []
        for c in lst.cards:
            if c.is_archived:
                continue
            cards.append({
                "id": c.id,
                "title": c.title,
                "description": c.description or "",
                "position": c.position,
                "due_date": c.due_date.isoformat() if c.due_date else None,
                "labels": [{"id": lb.id, "name": lb.name, "color": lb.color} for lb in c.labels],
                "members": [m.user_id for m in c.members],
                "checklist_progress": _checklist_progress(c),
                "comment_count": len(c.comments),
            })
        lists_data.append({"id": lst.id, "name": lst.name, "position": lst.position, "cards": cards})

    return {
        "id": board.id,
        "name": board.name,
        "background": board.background,
        "is_starred": board.is_starred,
        "lists": lists_data,
        "labels": [{"id": lb.id, "name": lb.name, "color": lb.color} for lb in board.labels],
        "members": [{"user_id": m.user_id, "role": m.role} for m in board.members],
    }


def _checklist_progress(card: Card) -> dict:
    total = sum(len(cl.items) for cl in card.checklists)
    done = sum(1 for cl in card.checklists for it in cl.items if it.is_checked)
    return {"done": done, "total": total}


@router.patch("/boards/{board_id}")
def update_board(board_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = svc.ensure_board_access(db, board_id, user)
    if "name" in payload:
        board.name = payload["name"]
    if "is_starred" in payload:
        board.is_starred = bool(payload["is_starred"])
    if "background" in payload:
        board.background = payload["background"]
    if "is_archived" in payload:
        board.is_archived = bool(payload["is_archived"])
    db.commit()
    return {"ok": True}


@router.post("/boards/{board_id}/lists", status_code=201)
def create_list(board_id: int, payload: ListCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    board = svc.ensure_board_access(db, board_id, user)
    pos = svc.next_position([l for l in board.lists if not l.is_archived])
    lst = BoardList(board_id=board.id, name=payload.name.strip(), position=pos)
    db.add(lst)
    svc.log_activity(db, board.id, user.id, "list.created", payload.name)
    db.commit()
    db.refresh(lst)
    return {"id": lst.id, "name": lst.name, "position": lst.position}


@router.patch("/lists/{list_id}")
def update_list(list_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(BoardList).filter(BoardList.id == list_id).first()
    if not lst:
        raise HTTPException(404, "List not found")
    svc.ensure_board_access(db, lst.board_id, user)
    if "name" in payload:
        lst.name = payload["name"]
    if "position" in payload:
        lst.position = float(payload["position"])
    if "is_archived" in payload:
        lst.is_archived = bool(payload["is_archived"])
    db.commit()
    return {"ok": True}


@router.post("/cards", status_code=201)
def create_card(payload: CardCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lst = db.query(BoardList).filter(BoardList.id == payload.list_id).first()
    if not lst:
        raise HTTPException(404, "List not found")
    board = svc.ensure_board_access(db, lst.board_id, user)
    pos = svc.next_position([c for c in lst.cards if not c.is_archived])
    card = Card(list_id=lst.id, title=payload.title.strip(), position=pos, created_by=user.id)
    db.add(card)
    db.flush()
    svc.log_activity(db, board.id, user.id, "card.created", payload.title, card_id=card.id)
    db.commit()
    db.refresh(card)
    return {"id": card.id, "title": card.title, "position": card.position, "list_id": card.list_id}


@router.get("/cards/{card_id}")
def get_card(card_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).options(
        joinedload(Card.labels),
        joinedload(Card.checklists).joinedload(Checklist.items),
        joinedload(Card.comments),
        joinedload(Card.members),
    ).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    svc.ensure_board_access(db, lst.board_id, user)
    return {
        "id": card.id,
        "title": card.title,
        "description": card.description or "",
        "due_date": card.due_date.isoformat() if card.due_date else None,
        "list_id": card.list_id,
        "labels": [{"id": l.id, "name": l.name, "color": l.color} for l in card.labels],
        "members": [m.user_id for m in card.members],
        "checklists": [
            {
                "id": cl.id,
                "title": cl.title,
                "items": [{"id": it.id, "text": it.text, "is_checked": it.is_checked} for it in cl.items],
            }
            for cl in card.checklists
        ],
        "comments": [
            {"id": cm.id, "user_id": cm.user_id, "body": cm.body, "created_at": cm.created_at.isoformat()}
            for cm in card.comments
        ],
    }


@router.patch("/cards/{card_id}")
def update_card(card_id: int, payload: CardUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    board = svc.ensure_board_access(db, lst.board_id, user)

    if payload.title is not None:
        card.title = payload.title.strip()
    if payload.description is not None:
        card.description = payload.description
    if payload.due_date is not None:
        card.due_date = payload.due_date
    if payload.list_id is not None:
        new_list = db.query(BoardList).filter(BoardList.id == payload.list_id, BoardList.board_id == board.id).first()
        if not new_list:
            raise HTTPException(400, "Invalid list")
        card.list_id = payload.list_id
        svc.log_activity(db, board.id, user.id, "card.moved", f"to list {new_list.name}", card_id=card.id)
    if payload.position is not None:
        card.position = payload.position
    db.commit()
    return {"ok": True}


@router.post("/cards/{card_id}/move")
def move_card(card_id: int, payload: CardMove, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    board = svc.ensure_board_access(db, lst.board_id, user)
    new_list = db.query(BoardList).filter(BoardList.id == payload.list_id, BoardList.board_id == board.id).first()
    if not new_list:
        raise HTTPException(400, "Invalid list")
    card.list_id = payload.list_id
    card.position = payload.position
    svc.log_activity(db, board.id, user.id, "card.moved", f"to {new_list.name}", card_id=card.id)
    db.commit()
    return {"ok": True}


@router.post("/cards/{card_id}/labels")
def toggle_label(card_id: int, payload: LabelToggle, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).options(joinedload(Card.labels)).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    board = svc.ensure_board_access(db, lst.board_id, user)
    label = db.query(Label).filter(Label.id == payload.label_id, Label.board_id == board.id).first()
    if not label:
        raise HTTPException(404, "Label not found")
    if label in card.labels:
        card.labels.remove(label)
    else:
        card.labels.append(label)
    db.commit()
    return {"ok": True}


@router.post("/cards/{card_id}/comments", status_code=201)
def add_comment(card_id: int, payload: CommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    board = svc.ensure_board_access(db, lst.board_id, user)
    cm = Comment(card_id=card.id, user_id=user.id, body=payload.body.strip())
    db.add(cm)
    svc.log_activity(db, board.id, user.id, "comment.added", payload.body[:80], card_id=card.id)
    db.commit()
    db.refresh(cm)
    return {"id": cm.id, "body": cm.body, "user_id": cm.user_id, "created_at": cm.created_at.isoformat()}


@router.post("/cards/{card_id}/checklists", status_code=201)
def add_checklist(card_id: int, payload: ChecklistCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card not found")
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    svc.ensure_board_access(db, lst.board_id, user)
    cl = Checklist(card_id=card.id, title=payload.title)
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return {"id": cl.id, "title": cl.title, "items": []}


@router.post("/checklists/{checklist_id}/items", status_code=201)
def add_checklist_item(checklist_id: int, payload: ChecklistItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cl = db.query(Checklist).filter(Checklist.id == checklist_id).first()
    if not cl:
        raise HTTPException(404, "Checklist not found")
    card = db.query(Card).filter(Card.id == cl.card_id).first()
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    svc.ensure_board_access(db, lst.board_id, user)
    item = ChecklistItem(checklist_id=cl.id, text=payload.text.strip(), position=svc.next_position(cl.items))
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "text": item.text, "is_checked": item.is_checked}


@router.patch("/checklist-items/{item_id}")
def toggle_checklist_item(item_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    cl = db.query(Checklist).filter(Checklist.id == item.checklist_id).first()
    card = db.query(Card).filter(Card.id == cl.card_id).first()
    lst = db.query(BoardList).filter(BoardList.id == card.list_id).first()
    svc.ensure_board_access(db, lst.board_id, user)
    if "is_checked" in payload:
        item.is_checked = bool(payload["is_checked"])
    if "text" in payload:
        item.text = payload["text"]
    db.commit()
    return {"ok": True}


@router.get("/boards/{board_id}/activity")
def board_activity(board_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.ensure_board_access(db, board_id, user)
    acts = (
        db.query(Activity)
        .filter(Activity.board_id == board_id)
        .order_by(Activity.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {"id": a.id, "action": a.action, "detail": a.detail, "user_id": a.user_id,
         "card_id": a.card_id, "created_at": a.created_at.isoformat()}
        for a in acts
    ]
