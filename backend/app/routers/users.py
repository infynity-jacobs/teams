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
def deactivate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = False
    db.commit()
    log_action(db, current_user, "deactivate_user", "user", user.id, request=request)
    return {"detail": "User deactivated"}
