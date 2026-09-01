from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import SettingOption, User
from app.schemas import SettingOptionCreate, SettingOptionUpdate, SettingOptionOut
from app.deps import get_current_user, require_roles, log_action, ADMINS

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/options", response_model=List[SettingOptionOut])
def list_options(
    category: Optional[str] = None,
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),  # any authenticated user - needed to populate dropdowns
    db: Session = Depends(get_db),
):
    q = db.query(SettingOption)
    if category:
        q = q.filter(SettingOption.category == category)
    if not include_inactive:
        q = q.filter(SettingOption.is_active.is_(True))
    return q.order_by(SettingOption.category, SettingOption.value).all()


@router.get("/categories", response_model=List[str])
def list_categories(
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    rows = db.query(SettingOption.category).distinct().all()
    return sorted({r[0] for r in rows})


@router.post("/options", response_model=SettingOptionOut)
def create_option(
    payload: SettingOptionCreate,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    category = payload.category.strip()
    value = payload.value.strip()
    if not category or not value:
        raise HTTPException(400, "category and value are required")

    existing = db.query(SettingOption).filter(
        SettingOption.category == category, SettingOption.value == value
    ).first()
    if existing:
        if existing.is_active:
            raise HTTPException(409, f"'{value}' already exists under '{category}'")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        log_action(db, current_user, "reactivate_setting_option", "setting_option", existing.id,
                   {"category": category, "value": value}, request)
        return existing

    option = SettingOption(category=category, value=value, created_by_id=current_user.id)
    db.add(option)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"'{value}' already exists under '{category}'")
    db.refresh(option)
    log_action(db, current_user, "create_setting_option", "setting_option", option.id,
               {"category": category, "value": value}, request)
    return option


@router.put("/options/{option_id}", response_model=SettingOptionOut)
def update_option(
    option_id: int,
    payload: SettingOptionUpdate,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    option = db.query(SettingOption).filter(SettingOption.id == option_id).first()
    if not option:
        raise HTTPException(404, "Option not found")

    data = payload.dict(exclude_unset=True)
    if "value" in data and data["value"]:
        data["value"] = data["value"].strip()
    for field, value in data.items():
        setattr(option, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An option with that value already exists in this category")
    db.refresh(option)
    log_action(db, current_user, "update_setting_option", "setting_option", option.id, data, request)
    return option


@router.delete("/options/{option_id}")
def deactivate_option(
    option_id: int,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    # Soft delete only: leads store the chosen value as plain text (not a
    # foreign key), so deactivating - rather than deleting - keeps historical
    # leads' "Referred By" values intact and readable while removing the
    # option from future dropdowns.
    option = db.query(SettingOption).filter(SettingOption.id == option_id).first()
    if not option:
        raise HTTPException(404, "Option not found")
    option.is_active = False
    db.commit()
    log_action(db, current_user, "deactivate_setting_option", "setting_option", option.id, request=request)
    return {"detail": "Option deactivated"}
