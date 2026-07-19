from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
import time

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import (
    hash_password, verify_password, rotate_session, destroy_session,
    get_session, check_rate, store_reset_token, consume_reset_token,
    generate_token, destroy_all_user_sessions, log_auth_event,
)
from app.models.user import User
from app.schemas.auth import (
    RegisterIn, LoginIn, PasswordResetRequestIn, PasswordResetConfirmIn,
    ChangePasswordIn, UserOut, MessageOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _uniform() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = _ip(request)
    ok, _ = check_rate("reg_ip", ip, 5, 60)
    if not ok:
        raise HTTPException(429, "Too many registration attempts")

    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        time.sleep(0.12)
        raise HTTPException(400, "Unable to create account with the provided data")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip() or payload.email.split("@")[0],
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Unable to create account with the provided data")

    log_auth_event("register", user.email, ip)
    return user


@router.post("/login", response_model=MessageOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _ip(request)
    email = payload.email.lower()

    ok_ip, _ = check_rate("login_ip", ip, settings.rate_limit_login_ip, 60)
    if not ok_ip:
        raise HTTPException(429, "Too many login attempts from this IP")
    ok_acc, _ = check_rate("login_acc", email, settings.rate_limit_login_account, 60)
    if not ok_acc:
        raise HTTPException(429, "Too many login attempts for this account")

    user = db.query(User).filter(User.email == email).first()
    dummy = "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy"
    password_ok = False

    if user and user.is_active:
        if user.is_locked():
            verify_password(payload.password, user.password_hash or dummy)
            log_auth_event("login_locked", email, ip)
            raise _uniform()
        password_ok = verify_password(payload.password, user.password_hash)
    else:
        verify_password(payload.password, dummy)

    if not user or not password_ok:
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.account_lockout_threshold:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.account_lockout_minutes)
            db.commit()
        log_auth_event("login_failed", email, ip)
        time.sleep(0.05)
        raise _uniform()

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    old = request.cookies.get(settings.session_cookie_name)
    sid = rotate_session(old, user.id, ip=ip, ua=request.headers.get("User-Agent"))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sid,
        max_age=settings.session_ttl_seconds,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    log_auth_event("login_success", email, ip)
    return MessageOut(detail="Login successful")


@router.post("/logout", response_model=MessageOut)
def logout(request: Request, response: Response):
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        destroy_session(sid)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageOut(detail="Logged out")


@router.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    sid = request.cookies.get(settings.session_cookie_name)
    sess = get_session(sid) if sid else None
    if not sess:
        raise HTTPException(401, "Not authenticated")
    user = db.query(User).filter(User.id == int(sess["user_id"]), User.is_active == True).first()
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/password-reset/request", response_model=MessageOut)
def password_reset_request(payload: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)):
    ip = _ip(request)
    ok, _ = check_rate("reset_ip", ip, 5, 60)
    if not ok:
        raise HTTPException(429, "Too many requests")

    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active == True).first()
    if user:
        token = generate_token(32)
        store_reset_token(user.id, token)
        log_auth_event("password_reset_requested", user.email, ip)
        if settings.debug:
            return MessageOut(detail=f"If the account exists, a reset link was generated. DEV token: {token}")
    else:
        time.sleep(0.1)
    return MessageOut(detail="If the account exists, a reset link was generated.")


@router.post("/password-reset/confirm", response_model=MessageOut)
def password_reset_confirm(payload: PasswordResetConfirmIn, request: Request, db: Session = Depends(get_db)):
    uid = consume_reset_token(payload.token)
    if not uid:
        raise HTTPException(400, "Invalid or expired token")
    user = db.query(User).filter(User.id == uid, User.is_active == True).first()
    if not user:
        raise HTTPException(400, "Invalid or expired token")
    user.password_hash = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    destroy_all_user_sessions(user.id)
    log_auth_event("password_reset_completed", user.email, _ip(request))
    return MessageOut(detail="Password updated. Please log in.")


@router.post("/change-password", response_model=MessageOut)
def change_password(payload: ChangePasswordIn, request: Request, db: Session = Depends(get_db)):
    sid = request.cookies.get(settings.session_cookie_name)
    sess = get_session(sid) if sid else None
    if not sess:
        raise HTTPException(401, "Not authenticated")
    user = db.query(User).filter(User.id == int(sess["user_id"])).first()
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    destroy_all_user_sessions(user.id, except_sid=sid)
    log_auth_event("password_changed", user.email, _ip(request))
    return MessageOut(detail="Password changed. Other sessions were revoked.")
