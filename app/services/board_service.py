"""Board / List / Card domain operations."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.board import Board, BoardMember, Label
from app.models.list_model import BoardList
from app.models.card import Card, CardMember, Checklist, ChecklistItem, Comment, Activity


def _now():
    return datetime.now(timezone.utc)


def ensure_board_access(db: Session, board_id: int, user: User, min_role: str = "member") -> Board:
    board = db.query(Board).options(
        joinedload(Board.lists).joinedload(BoardList.cards),
        joinedload(Board.labels),
        joinedload(Board.members),
    ).filter(Board.id == board_id, Board.is_archived == False).first()
    if not board:
        raise HTTPException(404, "Board not found")
    is_member = any(m.user_id == user.id for m in board.members) or board.owner_id == user.id
    if not is_member:
        raise HTTPException(403, "Access denied")
    return board


def create_default_workspace(db: Session, user: User) -> Workspace:
    ws = Workspace(name=f"{user.display_name}'s Workspace", owner_id=user.id)
    db.add(ws)
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
    )
    return ws


def get_or_create_default_workspace(db: Session, user: User) -> Workspace:
    mem = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    if mem:
        return db.query(Workspace).filter(Workspace.id == mem.workspace_id).first()
    ws = create_default_workspace(db, user)
    db.commit()
    db.refresh(ws)
    return ws


def create_board(db: Session, user: User, name: str, workspace_id: int | None = None) -> Board:
    if workspace_id:
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            raise HTTPException(404, "Workspace not found")
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id
        ).first()
        if not member:
            raise HTTPException(403, "Not a workspace member")
    else:
        ws = get_or_create_default_workspace(db, user)

    board = Board(name=name.strip(), workspace_id=ws.id, owner_id=user.id)
    db.add(board)
    db.flush()
    db.add(BoardMember(board_id=board.id, user_id=user.id, role="owner"))

    for i, title in enumerate(["To Do", "Doing", "Done"]):
        db.add(BoardList(board_id=board.id, name=title, position=float((i + 1) * 1000)))

    for name_l, color in [("Green", "#61bd4f"), ("Yellow", "#f2d600"), ("Orange", "#ff9f1a"),
                        ("Red", "#eb5a46"), ("Purple", "#c377e0"), ("Blue", "#0079bf")]:
        db.add(Label(board_id=board.id, name=name_l, color=color))

    db.add(Activity(board_id=board.id, user_id=user.id, action="board.created", detail=name))
    db.commit()
    db.refresh(board)
    return board


def log_activity(db: Session, board_id: int, user_id: int, action: str, detail: str = "", card_id: int | None = None):
    db.add(Activity(board_id=board_id, user_id=user_id, action=action, detail=detail, card_id=card_id))


def next_position(items) -> float:
    if not items:
        return 1000.0
    return max(i.position for i in items) + 1000.0
