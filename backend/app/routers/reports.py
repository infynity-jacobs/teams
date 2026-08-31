import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Lead, User, Team, LeadStatusEnum, RoleEnum
from app.deps import get_current_user
from app.routers.leads import _visible_leads_query
from app.utils.exporters import build_xlsx, build_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _apply_common_filters(q, date_from, date_to, team_id, staff_id, source, status):
    if date_from:
        q = q.filter(Lead.created_at >= date_from)
    if date_to:
        q = q.filter(Lead.created_at <= dt.datetime.combine(date_to, dt.time.max))
    if team_id:
        q = q.filter(Lead.team_id == team_id)
    if staff_id:
        q = q.filter(Lead.assigned_to_id == staff_id)
    if source:
        q = q.filter(Lead.source == source)
    if status:
        q = q.filter(Lead.status == status)
    return q


def _lead_rows(db: Session, leads):
    headers = ["ID", "Name", "Email", "Phone", "Company", "Source", "Status",
               "Assigned To", "Team", "Created", "Converted"]
    rows = []
    for l in leads:
        rows.append([
            l.id, f"{l.first_name} {l.last_name or ''}".strip(), l.email or "", l.phone or "",
            l.company or "", l.source or "", l.status.value,
            l.assigned_to.full_name if l.assigned_to else "",
            l.team.name if l.team else "",
            l.created_at.strftime("%Y-%m-%d") if l.created_at else "",
            l.converted_at.strftime("%Y-%m-%d") if l.converted_at else "",
        ])
    return headers, rows


@router.get("/leads")
def lead_lifecycle_report(
    stage: str = Query(..., description="new|pending|follow_up|converted|lost|closed|all"),
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    team_id: Optional[int] = None,
    staff_id: Optional[int] = None,
    source: Optional[str] = None,
    export: Optional[str] = Query(None, description="pdf|xlsx"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = _visible_leads_query(db, current_user)
    status = None if stage == "all" else LeadStatusEnum(stage)
    q = _apply_common_filters(q, date_from, date_to, team_id, staff_id, source, status)
    leads = q.order_by(Lead.created_at.desc()).all()

    headers, rows = _lead_rows(db, leads)

    if export == "xlsx":
        data = build_xlsx(headers, rows, title=f"{stage}_leads")
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={stage}_leads.xlsx"},
        )
    if export == "pdf":
        data = build_pdf(headers, rows, title=f"Lead Report: {stage.replace('_', ' ').title()}",
                          subtitle=f"Generated {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return StreamingResponse(
            iter([data]), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={stage}_leads.pdf"},
        )

    return {"stage": stage, "count": len(leads), "headers": headers, "rows": rows}


@router.get("/staff-performance")
def staff_performance_report(
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    team_id: Optional[int] = None,
    export: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = _visible_leads_query(db, current_user)
    base = _apply_common_filters(base, date_from, date_to, team_id, None, None, None)

    staff_q = db.query(User).filter(User.role == RoleEnum.marketing_staff)
    if current_user.role == RoleEnum.team_leader:
        staff_q = staff_q.filter(User.team_id == current_user.team_id)
    if team_id:
        staff_q = staff_q.filter(User.team_id == team_id)
    staff_list = staff_q.all()

    headers = ["Staff", "Team", "Total Leads", "New", "Follow-up", "Pending", "Converted", "Lost", "Conversion %"]
    rows = []
    for s in staff_list:
        leads = [l for l in base if l.assigned_to_id == s.id]
        total = len(leads)
        converted = sum(1 for l in leads if l.status == LeadStatusEnum.converted)
        conv_pct = round((converted / total) * 100, 1) if total else 0.0
        rows.append([
            s.full_name, s.team.name if s.team else "", total,
            sum(1 for l in leads if l.status == LeadStatusEnum.new),
            sum(1 for l in leads if l.status == LeadStatusEnum.follow_up),
            sum(1 for l in leads if l.status == LeadStatusEnum.pending),
            converted,
            sum(1 for l in leads if l.status == LeadStatusEnum.lost),
            conv_pct,
        ])

    if export == "xlsx":
        data = build_xlsx(headers, rows, title="staff_performance")
        return StreamingResponse(iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=staff_performance.xlsx"})
    if export == "pdf":
        data = build_pdf(headers, rows, title="Staff Performance Report")
        return StreamingResponse(iter([data]), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=staff_performance.pdf"})

    return {"headers": headers, "rows": rows}


@router.get("/team-performance")
def team_performance_report(
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    export: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = _visible_leads_query(db, current_user)
    base = _apply_common_filters(base, date_from, date_to, None, None, None, None)

    teams = db.query(Team).all()
    if current_user.role == RoleEnum.team_leader:
        teams = [t for t in teams if t.id == current_user.team_id]

    headers = ["Team", "Total Leads", "New", "Follow-up", "Pending", "Converted", "Lost", "Conversion %"]
    rows = []
    for t in teams:
        leads = [l for l in base if l.team_id == t.id]
        total = len(leads)
        converted = sum(1 for l in leads if l.status == LeadStatusEnum.converted)
        conv_pct = round((converted / total) * 100, 1) if total else 0.0
        rows.append([
            t.name, total,
            sum(1 for l in leads if l.status == LeadStatusEnum.new),
            sum(1 for l in leads if l.status == LeadStatusEnum.follow_up),
            sum(1 for l in leads if l.status == LeadStatusEnum.pending),
            converted,
            sum(1 for l in leads if l.status == LeadStatusEnum.lost),
            conv_pct,
        ])

    if export == "xlsx":
        data = build_xlsx(headers, rows, title="team_performance")
        return StreamingResponse(iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=team_performance.xlsx"})
    if export == "pdf":
        data = build_pdf(headers, rows, title="Team Performance Report")
        return StreamingResponse(iter([data]), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=team_performance.pdf"})

    return {"headers": headers, "rows": rows}


@router.get("/conversion-stats")
def conversion_stats(
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    team_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = _visible_leads_query(db, current_user)
    q = _apply_common_filters(q, date_from, date_to, team_id, None, None, None)
    leads = q.all()
    total = len(leads)
    by_status = {}
    for st in LeadStatusEnum:
        by_status[st.value] = sum(1 for l in leads if l.status == st)
    converted = by_status.get("converted", 0)
    return {
        "total_leads": total,
        "by_status": by_status,
        "conversion_rate": round((converted / total) * 100, 1) if total else 0.0,
    }


@router.get("/sources")
def sources_list(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _visible_leads_query(db, current_user)
    rows = q.with_entities(Lead.source).distinct().all()
    return sorted({r[0] for r in rows if r[0]})
