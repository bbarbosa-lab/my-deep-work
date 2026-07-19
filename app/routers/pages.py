from pathlib import Path
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_optional, get_current_user
from app.models.user import User
from app.services import board_service as svc

router = APIRouter(tags=["pages"])
BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/boards", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/boards", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request, "user": None})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/boards", status_code=303)
    return templates.TemplateResponse("auth/register.html", {"request": request, "user": None})


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_page(request: Request):
    return templates.TemplateResponse("auth/forgot.html", {"request": request, "user": None})


@router.get("/reset-password", response_class=HTMLResponse)
def reset_page(request: Request, token: str = ""):
    return templates.TemplateResponse("auth/reset.html", {"request": request, "user": None, "token": token})


@router.get("/boards", response_class=HTMLResponse)
def boards_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("boards/home.html", {"request": request, "user": user})


@router.get("/boards/{board_id}", response_class=HTMLResponse)
def board_page(board_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.ensure_board_access(db, board_id, user)
    return templates.TemplateResponse("boards/board.html", {"request": request, "user": user, "board_id": board_id})


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("auth/settings.html", {"request": request, "user": user})
