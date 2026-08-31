from typing import List, Optional
import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogOut
from app.deps import require_roles, ADMINS

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogOut])
def list_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if date_from:
        q = q.filter(AuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.created_at <= dt.datetime.combine(date_to, dt.time.max))
    q = q.order_by(AuditLog.created_at.desc())
    return q.offset((page - 1) * page_size).limit(page_size).all()
