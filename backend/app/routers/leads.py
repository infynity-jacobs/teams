import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Lead, User, Team, RoleEnum, LeadStatusHistory, FollowUp, LeadStatusEnum
from app.schemas import (
    LeadCreate, LeadUpdate, LeadOut, LeadListOut, LeadStatusChange, LeadAssign,
    LeadDetailOut, FollowUpCreate, FollowUpOut,
)
from app.deps import get_current_user, require_roles, log_action, LEADERS_UP, ALL_STAFF

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _normalize(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def _dedup_key(email: Optional[str], phone: Optional[str]) -> Optional[str]:
    if email:
        return f"email:{_normalize(email)}"
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits:
            return f"phone:{digits}"
    return None


def _visible_leads_query(db: Session, user: User):
    q = db.query(Lead)
    if user.role in (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager):
        return q  # full visibility
    if user.role == RoleEnum.team_leader:
        return q.filter(Lead.team_id == user.team_id)
    # marketing_staff: only their own assigned leads
    return q.filter(Lead.assigned_to_id == user.id)


def _to_out(lead: Lead) -> LeadOut:
    data = LeadOut.model_validate(lead)
    data.assigned_to_name = lead.assigned_to.full_name if lead.assigned_to else None
    data.team_name = lead.team.name if lead.team else None
    return data


@router.get("", response_model=LeadListOut)
def list_leads(
    status: Optional[LeadStatusEnum] = None,
    team_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
    source: Optional[str] = None,
    place_area: Optional[str] = None,
    referred_by: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = _visible_leads_query(db, current_user)
    if status:
        q = q.filter(Lead.status == status)
    if team_id:
        q = q.filter(Lead.team_id == team_id)
    if assigned_to_id:
        q = q.filter(Lead.assigned_to_id == assigned_to_id)
    if source:
        q = q.filter(Lead.source == source)
    if place_area:
        q = q.filter(Lead.place_area == place_area)
    if referred_by:
        q = q.filter(Lead.referred_by == referred_by)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            Lead.first_name.ilike(like), Lead.last_name.ilike(like),
            Lead.email.ilike(like), Lead.phone.ilike(like), Lead.company.ilike(like),
            Lead.place_area.ilike(like),
        ))
    if date_from:
        q = q.filter(Lead.created_at >= date_from)
    if date_to:
        q = q.filter(Lead.created_at <= dt.datetime.combine(date_to, dt.time.max))

    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return LeadListOut(total=total, items=[_to_out(l) for l in items])


@router.post("", response_model=LeadOut)
def create_lead(
    payload: LeadCreate,
    request: Request,
    current_user: User = Depends(require_roles(*ALL_STAFF)),
    db: Session = Depends(get_db),
):
    dedup = _dedup_key(payload.email, payload.phone)
    if dedup:
        existing = db.query(Lead).filter(Lead.dedup_key == dedup).first()
        if existing:
            raise HTTPException(409, f"A lead with this email/phone already exists (id={existing.id})")

    lead = Lead(
        **payload.dict(exclude={"status"}),
        status=payload.status or LeadStatusEnum.new,
        dedup_key=dedup,
        created_by_id=current_user.id,
    )
    if current_user.role == RoleEnum.marketing_staff and not lead.assigned_to_id:
        lead.assigned_to_id = current_user.id
        lead.team_id = lead.team_id or current_user.team_id
    if current_user.role == RoleEnum.team_leader and not lead.team_id:
        lead.team_id = current_user.team_id

    db.add(lead)
    db.commit()
    db.refresh(lead)

    db.add(LeadStatusHistory(lead_id=lead.id, old_status=None, new_status=lead.status.value,
                              changed_by_id=current_user.id, note="Lead created"))
    db.commit()
    log_action(db, current_user, "create_lead", "lead", lead.id, {"name": lead.first_name}, request)
    return _to_out(lead)


def _get_lead_or_404(db: Session, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


def _check_visibility(user: User, lead: Lead):
    if user.role in (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager):
        return
    if user.role == RoleEnum.team_leader and lead.team_id == user.team_id:
        return
    if user.role == RoleEnum.marketing_staff and lead.assigned_to_id == user.id:
        return
    raise HTTPException(403, "You do not have access to this lead")


@router.get("/{lead_id}", response_model=LeadDetailOut)
def get_lead(lead_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, lead_id)
    _check_visibility(current_user, lead)
    out = LeadDetailOut.model_validate(lead)
    out.assigned_to_name = lead.assigned_to.full_name if lead.assigned_to else None
    out.team_name = lead.team.name if lead.team else None
    out.history = sorted(lead.history, key=lambda h: h.changed_at, reverse=True)
    out.follow_ups = sorted(lead.follow_ups, key=lambda f: f.created_at, reverse=True)
    return out


@router.put("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int, payload: LeadUpdate, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_id)
    _check_visibility(current_user, lead)

    data = payload.dict(exclude_unset=True)
    # Only leaders and above may reassign / re-team via this endpoint.
    if ("assigned_to_id" in data or "team_id" in data) and current_user.role not in LEADERS_UP:
        raise HTTPException(403, "Only Team Leaders and above may reassign leads")

    # Validate the resulting team/assignee combination server-side so the UI
    # cannot be bypassed with an inconsistent assignment.
    if "assigned_to_id" in data and data["assigned_to_id"] is not None:
        staff = db.query(User).filter(User.id == data["assigned_to_id"]).first()
        if not staff:
            raise HTTPException(404, "Staff member not found")
        if staff.role != RoleEnum.marketing_staff:
            raise HTTPException(400, "Leads can only be assigned to Marketing Staff")
        target_team_id = data.get("team_id", lead.team_id)
        if target_team_id is not None and staff.team_id != target_team_id:
            raise HTTPException(400, "Assigned staff member must belong to the selected team")
        if current_user.role == RoleEnum.team_leader and staff.team_id != current_user.team_id:
            raise HTTPException(403, "Can only assign to members of your own team")

    if "team_id" in data and data["team_id"] is not None:
        team = db.query(Team).filter(Team.id == data["team_id"], Team.is_active == True).first()
        if not team:
            raise HTTPException(404, "Team not found or inactive")
        if current_user.role == RoleEnum.team_leader and team.id != current_user.team_id:
            raise HTTPException(403, "Can only assign leads to your own team")
        existing_assignee_id = data.get("assigned_to_id", lead.assigned_to_id)
        if existing_assignee_id is not None:
            staff = db.query(User).filter(User.id == existing_assignee_id).first()
            if not staff or staff.team_id != team.id:
                raise HTTPException(400, "Assigned staff member must belong to the selected team")

    for field, value in data.items():
        setattr(lead, field, value)
    if "email" in data or "phone" in data:
        lead.dedup_key = _dedup_key(lead.email, lead.phone)

    db.commit()
    db.refresh(lead)
    log_action(db, current_user, "update_lead", "lead", lead.id, data, request)
    return _to_out(lead)


@router.post("/{lead_id}/assign", response_model=LeadOut)
def assign_lead(
    lead_id: int, payload: LeadAssign, request: Request,
    current_user: User = Depends(require_roles(*LEADERS_UP)), db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_id)
    if current_user.role not in (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager):
        _check_visibility(current_user, lead)

    staff = db.query(User).filter(User.id == payload.assigned_to_id).first()
    if not staff:
        raise HTTPException(404, "Staff member not found")
    if staff.role != RoleEnum.marketing_staff:
        raise HTTPException(400, "Leads can only be assigned to Marketing Staff")
    if current_user.role == RoleEnum.team_leader and staff.team_id != current_user.team_id:
        raise HTTPException(403, "Can only assign to members of your own team")

    lead.assigned_to_id = staff.id
    if staff.team_id:
        lead.team_id = staff.team_id
    db.commit()
    db.refresh(lead)
    log_action(db, current_user, "assign_lead", "lead", lead.id, {"assigned_to_id": staff.id}, request)
    return _to_out(lead)


@router.post("/{lead_id}/status", response_model=LeadOut)
def change_status(
    lead_id: int, payload: LeadStatusChange, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_id)
    _check_visibility(current_user, lead)

    old_status = lead.status.value
    lead.status = payload.status
    if payload.status == LeadStatusEnum.converted:
        lead.converted_at = dt.datetime.utcnow()
    elif old_status == LeadStatusEnum.converted.value:
        # Moving a converted lead back into the sales pipeline makes the
        # existing conversion eligible for a later re-conversion.
        lead.converted_at = None
    if payload.status == LeadStatusEnum.lost:
        lead.lost_reason = payload.lost_reason

    db.add(LeadStatusHistory(
        lead_id=lead.id, old_status=old_status, new_status=payload.status.value,
        changed_by_id=current_user.id, note=payload.note,
    ))
    db.commit()
    db.refresh(lead)
    log_action(db, current_user, "change_status", "lead", lead.id,
               {"from": old_status, "to": payload.status.value}, request)
    return _to_out(lead)


@router.post("/{lead_id}/follow-ups", response_model=FollowUpOut)
def add_follow_up(
    lead_id: int, payload: FollowUpCreate, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_id)
    _check_visibility(current_user, lead)

    fu = FollowUp(lead_id=lead.id, staff_id=current_user.id, **payload.dict())
    db.add(fu)
    # A follow-up naturally implies the lead has moved from "new" into the pipeline
    if lead.status == LeadStatusEnum.new:
        lead.status = LeadStatusEnum.follow_up
        db.add(LeadStatusHistory(lead_id=lead.id, old_status="new", new_status="follow_up",
                                  changed_by_id=current_user.id, note="Follow-up logged"))
    db.commit()
    db.refresh(fu)
    log_action(db, current_user, "add_follow_up", "lead", lead.id, {"type": fu.follow_up_type}, request)
    return fu


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int, request: Request,
    current_user: User = Depends(require_roles(*LEADERS_UP)), db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_id)
    db.delete(lead)
    db.commit()
    log_action(db, current_user, "delete_lead", "lead", lead_id, request=request)
    return {"detail": "Lead deleted"}
