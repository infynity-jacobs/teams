from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RoleEnum
from app.schemas import UserOut, UserCreate, UserUpdate
from app.deps import get_current_user, require_roles, log_action, ADMINS
from app.utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(
    team_id: Optional[int] = None,
    role: Optional[RoleEnum] = None,
    current_user: User = Depends(require_roles(*ADMINS, RoleEnum.marketing_manager, RoleEnum.team_leader)),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    # Team leaders only see their own team's staff
    if current_user.role == RoleEnum.team_leader:
        q = q.filter(User.team_id == current_user.team_id)
    if team_id:
        q = q.filter(User.team_id == team_id)
    if role:
        q = q.filter(User.role == role)
    return q.order_by(User.full_name).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email already exists")

    # Only super_admin may create another super_admin or site_admin
    if payload.role in (RoleEnum.super_admin, RoleEnum.site_admin) and current_user.role != RoleEnum.super_admin:
        raise HTTPException(403, "Only Super Admins may create admin accounts")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        team_id=payload.team_id,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, current_user, "create_user", "user", user.id, {"username": user.username}, request)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    # A non-Super-Admin cannot modify an administrator account, including
    # changing its password, role, email, name, team, or active state.
    if user.role in (RoleEnum.super_admin, RoleEnum.site_admin) and current_user.role != RoleEnum.super_admin:
        raise HTTPException(403, "Only Super Admins may modify administrator accounts")

    if payload.role in (RoleEnum.super_admin, RoleEnum.site_admin) and current_user.role != RoleEnum.super_admin:
        raise HTTPException(403, "Only Super Admins may assign admin roles")

    data = payload.dict(exclude_unset=True)
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    log_action(db, current_user, "update_user", "user", user.id, data, request)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_roles(RoleEnum.super_admin)),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == current_user.id:
        raise HTTPException(400, "You cannot delete your own account")
    # Preserve historical accountability. Users referenced by CRM history
    # cannot be hard-deleted; Super Admin must deactivate them instead.
    from app.models import Lead, FollowUp, LeadStatusHistory, ImportBatch, AuditLog, SystemSetting, PasswordResetToken, SettingOption, Conversion
    dependencies = {
        "leads": db.query(Lead).filter((Lead.assigned_to_id == user_id) | (Lead.created_by_id == user_id)).count(),
        "follow_ups": db.query(FollowUp).filter(FollowUp.staff_id == user_id).count(),
        "status_history": db.query(LeadStatusHistory).filter(LeadStatusHistory.changed_by_id == user_id).count(),
        "imports": db.query(ImportBatch).filter(ImportBatch.imported_by_id == user_id).count(),
        "audit_logs": db.query(AuditLog).filter(AuditLog.user_id == user_id).count(),
        "settings": db.query(SystemSetting).filter(SystemSetting.updated_by_id == user_id).count(),
        "reset_tokens": db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).count(),
        "options": db.query(SettingOption).filter(SettingOption.created_by_id == user_id).count(),
        "conversions": db.query(Conversion).filter(Conversion.converted_by_id == user_id).count(),
        "team_leader": db.query(__import__('app.models', fromlist=['Team']).Team).filter(__import__('app.models', fromlist=['Team']).Team.leader_id == user_id).count(),
    }
    used=[k for k,v in dependencies.items() if v]
    if used:
        raise HTTPException(409, "User has historical or active records and cannot be permanently deleted; deactivate the user instead. References: " + ", ".join(used))
    db.delete(user); db.commit()
    log_action(db, current_user, "delete_user", "user", user_id, {"username": user.username}, request)
    return {"detail": "User deleted"}
