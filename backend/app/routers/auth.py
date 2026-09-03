from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import datetime as dt

from app.database import get_db
from app.models import User, PasswordResetToken, SystemSetting, RoleEnum
from app.schemas import Token, UserOut, PasswordResetRequest, PasswordResetConfirm, PasswordChangeRequest
from app.utils.security import (
    verify_password, hash_password, create_access_token, new_reset_token, hash_reset_token
)
from app.utils.email import send_email, send_password_reset
from app.deps import log_action, get_current_user, require_roles, ADMINS
from app.config import settings


def _reset_minutes(db):
    row = db.query(SystemSetting).filter(SystemSetting.key == "password_reset_expire_minutes").first()
    try: return int(row.value) if row and row.value else settings.PASSWORD_RESET_EXPIRE_MINUTES
    except ValueError: return settings.PASSWORD_RESET_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public_base_url(request: Request) -> str:
    """Return the public browser-facing origin when behind Nginx/Cloudflare.

    Nginx overwrites Host and X-Forwarded-Proto for requests proxied to
    Uvicorn, so reset links are generated from the public hostname instead
    of an internal 127.0.0.1:8000/http origin. A configured frontend_url in
    System Settings still takes precedence inside send_password_reset().
    """
    forwarded_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    forwarded_proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        if user: log_action(db, user, "login_failed", "user", user.id, request=request)
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    timeout = db.query(SystemSetting).filter(SystemSetting.key == "session_timeout_minutes").first()
    try: timeout_minutes = int(timeout.value) if timeout and timeout.value else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    except ValueError: timeout_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token({"sub": str(user.id), "role": user.role.value, "sv": user.session_version}, expires_minutes=max(15, timeout_minutes))
    log_action(db, user, "login", "user", user.id, request=request)
    return Token(access_token=token, role=user.role.value, full_name=user.full_name, user_id=user.id)


@router.post("/forgot-password")
def forgot_password(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    # Deliberately generic response prevents account enumeration.
    user = db.query(User).filter((User.email == payload.identifier) | (User.username == payload.identifier)).first()
    if user and user.is_active:
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).update({"used_at": dt.datetime.utcnow()})
        raw = new_reset_token()
        token = PasswordResetToken(
            user_id=user.id, token_hash=hash_reset_token(raw),
            expires_at=dt.datetime.utcnow() + dt.timedelta(minutes=_reset_minutes(db))
        )
        db.add(token); db.commit()
        try:
            send_password_reset(db, user, raw, _public_base_url(request))
            log_action(db, user, "password_reset_requested", "user", user.id, request=request)
        except Exception:
            token.used_at = dt.datetime.utcnow(); db.commit()
            # Do not disclose SMTP/account state.
    return {"detail": "If the account exists, a password reset email has been sent."}


@router.post("/reset-password")
def reset_password(payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hash_reset_token(payload.token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > dt.datetime.utcnow()
    ).first()
    if not row:
        raise HTTPException(400, "Invalid or expired password reset link")
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(400, "Invalid password reset link")
    user.hashed_password = hash_password(payload.new_password)
    user.session_version = (user.session_version or 0) + 1
    row.used_at = dt.datetime.utcnow()
    # Invalidate every other outstanding token for the account.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != row.id,
        PasswordResetToken.used_at.is_(None)
    ).update({"used_at": dt.datetime.utcnow()})
    db.commit()
    try:
        send_email(db, [user.email], "Password changed successfully",
                   "Your Lead CRM password was changed successfully. If you did not make this change, contact an administrator immediately.")
    except Exception:
        pass
    log_action(db, user, "password_reset_completed", "user", user.id, request=request)
    return {"detail": "Password changed successfully"}


@router.post("/change-password")
def change_password(payload: PasswordChangeRequest, request: Request,
                    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.session_version = (current_user.session_version or 0) + 1
    db.commit()
    log_action(db, current_user, "change_password", "user", current_user.id, request=request)
    return {"detail": "Password changed successfully"}


@router.post("/admin-reset-password")
def admin_reset_password(user_id: int, request: Request,
                         current_user: User = Depends(require_roles(*ADMINS)),
                         db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")

    # Privilege boundary: only Super Admins may reset an admin account.
    # Site Admins and other non-Super-Admins may not reset Super Admins
    # (or Site Admins), even though they may have access to user management.
    if user.role in (RoleEnum.super_admin, RoleEnum.site_admin) and current_user.role != RoleEnum.super_admin:
        raise HTTPException(403, "Only Super Admins may reset administrator passwords")

    raw = new_reset_token()
    row = PasswordResetToken(
        user_id=user.id, token_hash=hash_reset_token(raw),
        expires_at=dt.datetime.utcnow() + dt.timedelta(minutes=_reset_minutes(db))
    )
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({"used_at": dt.datetime.utcnow()})
    user.session_version = (user.session_version or 0) + 1
    db.add(row); db.commit()
    try:
        send_password_reset(db, user, raw, _public_base_url(request))
    except Exception as exc:
        row.used_at = dt.datetime.utcnow(); db.commit()
        raise HTTPException(400, f"Could not send reset email: {exc}")
    log_action(db, current_user, "admin_password_reset", "user", user.id, request=request)
    return {"detail": "Password reset email sent"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
