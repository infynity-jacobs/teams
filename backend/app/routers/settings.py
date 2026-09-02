from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pathlib import Path
import os, uuid

from app.config import settings
from app.database import get_db
from app.models import SettingOption, SystemSetting, User, RoleEnum
from app.schemas import (
    SettingOptionCreate, SettingOptionUpdate, SettingOptionOut,
    SystemSettingOut, SystemSettingsUpdate, TestEmailRequest,
)
from app.deps import get_current_user, require_roles, log_action, ADMINS
from app.utils.security import encrypt_secret
from app.utils.email import send_email

router = APIRouter(prefix="/api/settings", tags=["settings"])

PUBLIC_KEYS = {
    "site_name", "company_name", "company_logo_url", "favicon_url", "login_branding",
    "theme", "primary_color", "contact_email", "contact_phone", "company_address",
    "timezone", "date_format", "locale",
}

DEFAULTS = {
    "site_name": "Lead CRM", "company_name": "", "company_logo_url": "",
    "favicon_url": "", "login_branding": "Marketing Lead Management",
    "theme": "light", "primary_color": "#0d6efd", "contact_email": "",
    "contact_phone": "", "company_address": "", "timezone": "Asia/Kolkata",
    "date_format": "DD MMM YYYY", "locale": "en-IN", "frontend_url": "",
    "smtp_host": "", "smtp_port": "587", "smtp_security": "starttls",
    "smtp_username": "", "smtp_password": "", "smtp_sender_email": "",
    "smtp_sender_name": "", "password_reset_expire_minutes": "30",
    "session_timeout_minutes": "480", "default_report_format": "pdf", "report_email_footer": "",
}


def _setting_map(db):
    rows = db.query(SystemSetting).all()
    result = DEFAULTS.copy()
    for r in rows:
        if r.is_secret:
            result[r.key] = "********"
        else:
            result[r.key] = r.value or ""
    return result


@router.get("/public", response_model=dict)
def public_settings(db: Session = Depends(get_db)):
    values = _setting_map(db)
    return {k: values.get(k, "") for k in PUBLIC_KEYS}


@router.get("/system", response_model=dict)
def system_settings(current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    return _setting_map(db)


@router.put("/system", response_model=dict)
def update_system_settings(payload: SystemSettingsUpdate, request: Request,
                           current_user: User = Depends(require_roles(*ADMINS)),
                           db: Session = Depends(get_db)):
    allowed = set(DEFAULTS)
    for key, value in payload.values.items():
        if key not in allowed:
            continue
        if key == "smtp_password" and str(value).strip() in ("", "********"):
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        secret = key == "smtp_password"
        stored = encrypt_secret(str(value)) if secret and value else str(value)
        if row:
            row.value = stored
            row.is_secret = secret
            row.updated_by_id = current_user.id
        else:
            db.add(SystemSetting(key=key, value=stored, is_secret=secret, updated_by_id=current_user.id))
    db.commit()
    log_action(db, current_user, "update_system_settings", "settings", None,
               {"keys": sorted(set(payload.values) & allowed)}, request)
    return _setting_map(db)


@router.post("/upload")
async def upload_brand_asset(file: UploadFile = File(...), kind: str = "logo",
                             request: Request = None,
                             current_user: User = Depends(require_roles(*ADMINS)),
                             db: Session = Depends(get_db)):
    if kind not in {"logo", "favicon"}:
        raise HTTPException(400, "kind must be logo or favicon")
    ext = Path(file.filename or "").suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".svg"}
    if ext not in allowed:
        raise HTTPException(400, "Unsupported image format")
    upload_dir = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{kind}-{uuid.uuid4().hex}{ext}"
    target = upload_dir / filename
    target.write_bytes(await file.read())
    key = "company_logo_url" if kind == "logo" else "favicon_url"
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    url = f"/uploads/{filename}"
    if row: row.value = url; row.updated_by_id = current_user.id
    else: db.add(SystemSetting(key=key, value=url, is_secret=False, updated_by_id=current_user.id))
    db.commit()
    log_action(db, current_user, "upload_brand_asset", "settings", None, {"kind": kind}, request)
    return {"url": url}


@router.get("/options", response_model=List[SettingOptionOut])
def list_options(category: Optional[str] = None, include_inactive: bool = False,
                 current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(SettingOption)
    if category: q = q.filter(SettingOption.category == category)
    if not include_inactive: q = q.filter(SettingOption.is_active.is_(True))
    return q.order_by(SettingOption.category, SettingOption.value).all()


@router.get("/categories", response_model=List[str])
def list_categories(current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    rows = db.query(SettingOption.category).distinct().all()
    return sorted({r[0] for r in rows})


@router.post("/options", response_model=SettingOptionOut)
def create_option(payload: SettingOptionCreate, request: Request,
                  current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    category, value = payload.category.strip(), payload.value.strip()
    if not category or not value: raise HTTPException(400, "category and value are required")
    existing = db.query(SettingOption).filter(SettingOption.category == category,
                                               SettingOption.value == value).first()
    if existing:
        if existing.is_active: raise HTTPException(409, f"'{value}' already exists under '{category}'")
        existing.is_active = True; db.commit(); db.refresh(existing)
        log_action(db, current_user, "reactivate_setting_option", "setting_option", existing.id, {"category": category, "value": value}, request)
        return existing
    option = SettingOption(category=category, value=value, created_by_id=current_user.id)
    db.add(option)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "That option already exists")
    db.refresh(option)
    log_action(db, current_user, "create_setting_option", "setting_option", option.id, {"category": category, "value": value}, request)
    return option


@router.put("/options/{option_id}", response_model=SettingOptionOut)
def update_option(option_id: int, payload: SettingOptionUpdate, request: Request,
                  current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    option = db.query(SettingOption).filter(SettingOption.id == option_id).first()
    if not option: raise HTTPException(404, "Option not found")
    data = payload.model_dump(exclude_unset=True)
    if "value" in data and data["value"]: data["value"] = data["value"].strip()
    for field, value in data.items(): setattr(option, field, value)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Duplicate setting option")
    db.refresh(option)
    log_action(db, current_user, "update_setting_option", "setting_option", option.id, data, request)
    return option


@router.delete("/options/{option_id}")
def deactivate_option(option_id: int, request: Request,
                      current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    option = db.query(SettingOption).filter(SettingOption.id == option_id).first()
    if not option: raise HTTPException(404, "Option not found")
    option.is_active = False; db.commit()
    log_action(db, current_user, "deactivate_setting_option", "setting_option", option.id, request=request)
    return {"detail": "Option deactivated"}


@router.post("/test-email")
def test_email(payload: TestEmailRequest, request: Request,
               current_user: User = Depends(require_roles(*ADMINS)), db: Session = Depends(get_db)):
    try:
        send_email(db, [payload.recipient], "Lead CRM SMTP test",
                   f"SMTP configuration test successful.\n\nSent by {current_user.full_name}.")
    except Exception as exc:
        log_action(db, current_user, "smtp_test_failed", "settings", None, {"error": str(exc)}, request)
        raise HTTPException(400, f"SMTP test failed: {exc}")
    log_action(db, current_user, "smtp_test_email", "settings", None, {"recipient": payload.recipient}, request)
    return {"detail": "Test email sent successfully"}
