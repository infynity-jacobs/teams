from typing import List

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RoleEnum, AuditLog
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active or int(payload.get("sv", 0)) != int(user.session_version or 0):
        raise credentials_exception
    return user


def require_roles(*roles: RoleEnum):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return checker


# Convenience role groups
ADMINS = (RoleEnum.super_admin, RoleEnum.site_admin)
MANAGERS_UP = (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager)
LEADERS_UP = (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager, RoleEnum.team_leader)
ALL_STAFF = (
    RoleEnum.super_admin,
    RoleEnum.site_admin,
    RoleEnum.marketing_manager,
    RoleEnum.team_leader,
    RoleEnum.marketing_staff,
)


def log_action(db: Session, user: User, action: str, entity_type: str = None,
                entity_id: int = None, details: dict = None, request: Request = None):
    ip = None
    if request is not None:
        ip = request.client.host if request.client else None
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip,
    )
    db.add(entry)
    db.commit()
