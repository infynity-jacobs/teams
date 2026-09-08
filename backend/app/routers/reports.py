import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Lead, User, Team, FollowUp, LeadStatusEnum, RoleEnum, SystemSetting, Product, LeadProduct, Conversion, ConversionItem
from app.deps import get_current_user
from app.routers.leads import _visible_leads_query
from app.utils.exporters import build_xlsx, build_pdf
from app.schemas import ReportEmailRequest
from app.deps import require_roles, ALL_STAFF, log_action
from app.utils.email import send_email

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _report_branding(db: Session):
    """Resolve report branding to server-local assets so PDFs do not depend on HTTP."""
    values = {r.key: (r.value or "") for r in db.query(SystemSetting).filter(SystemSetting.is_secret.is_(False)).all()}
    logo_url = values.get("company_logo_url", "")
    logo_path = None
    if logo_url:
        from pathlib import Path
        import os
        filename = logo_url.rsplit("/", 1)[-1]
        candidates = []
        configured = os.getenv("UPLOAD_DIR", "").strip()
        if configured:
            configured_path = Path(configured)
            if not configured_path.is_absolute():
                configured_path = Path(__file__).resolve().parents[2] / configured_path
            candidates.append(configured_path / filename)
        # The application convention is backend/uploads; resolve it from the
        # source tree as well as the process working directory for robustness.
        candidates.extend([
            # Canonical production upload directory: /opt/leadcrm/uploads
            Path(__file__).resolve().parents[3] / "uploads" / filename,
            # Backward-compatible locations for older installations.
            Path(__file__).resolve().parents[2] / "uploads" / filename,
            Path("./uploads") / filename,
        ])
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                logo_path = candidate
                break
    return {
        "company_name": values.get("company_name", ""),
        "site_name": values.get("site_name", "Lead CRM"),
        "company_address": values.get("company_address", ""),
        "contact_phone": values.get("contact_phone", ""),
        "contact_email": values.get("contact_email", ""),
        "report_email_footer": values.get("report_email_footer", ""),
        "logo_path": logo_path,
    }


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


def _sales_rows(db: Session, current_user: User, date_from=None, date_to=None, team_id=None, staff_id=None, source=None):
    """Return conversion line items with historical seller attribution."""
    visible_ids = {x.id for x in _visible_leads_query(db, current_user).all()}
    if not visible_ids:
        return []
    q = (db.query(ConversionItem, Conversion, Lead)
         .join(Conversion, ConversionItem.conversion_id == Conversion.id)
         .join(Lead, Conversion.lead_id == Lead.id)
         .filter(Lead.id.in_(visible_ids)))
    if date_from:
        q = q.filter(Conversion.conversion_date >= date_from)
    if date_to:
        q = q.filter(Conversion.conversion_date <= dt.datetime.combine(date_to, dt.time.max))
    if source:
        q = q.filter(Lead.source == source)
    selected_team_name = db.query(Team.name).filter(Team.id == team_id).scalar() if team_id else None
    rows = []
    for item, conversion, lead in q.order_by(Conversion.conversion_date.desc(), ConversionItem.id.asc()).all():
        seller_id = conversion.sold_by_id or lead.assigned_to_id
        seller_name = conversion.sold_by_name
        seller_username = conversion.sold_by_username
        seller_team = conversion.sold_by_team_name
        if not seller_name and lead.assigned_to:
            seller_name = lead.assigned_to.full_name
            seller_username = lead.assigned_to.username
            seller_team = lead.assigned_to.team.name if lead.assigned_to.team else None
        # Never attribute a sale to a non-marketing-staff converter. A legacy
        # conversion without a seller snapshot falls back to the lead assignment.
        if seller_id and conversion.sold_by_id is None:
            assigned = lead.assigned_to
            if not assigned or assigned.role != RoleEnum.marketing_staff:
                seller_id = None
                seller_name = seller_username = seller_team = None
        if selected_team_name and (seller_team or "") != selected_team_name:
            continue
        if staff_id and seller_id != staff_id:
            continue
        rows.append({
            "item": item, "conversion": conversion, "lead": lead,
            "seller_id": seller_id, "seller_name": seller_name or "Unassigned",
            "seller_username": seller_username or "", "seller_team": seller_team or "",
        })
    return rows


def _product_interest_rows(db: Session, current_user: User, date_from=None, date_to=None, team_id=None, staff_id=None, source=None):
    """Return product interests for visible leads, attributed to the assigned staff.

    This complements conversion-item sales data so the reports do not become
    empty merely because a product has been attached to a lead but the sale
    has not yet been recorded as a conversion. Interest data is never counted
    as sold units or revenue.
    """
    q = (db.query(LeadProduct, Lead)
         .join(Lead, LeadProduct.lead_id == Lead.id)
         .filter(Lead.id.in_(db.query(_visible_leads_query(db, current_user).with_entities(Lead.id).subquery()))))
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
    rows = []
    for lp, lead in q.order_by(Lead.created_at.desc(), LeadProduct.id.asc()).all():
        seller = lead.assigned_to
        seller_id = seller.id if seller else None
        seller_name = seller.full_name if seller else "Unassigned"
        seller_team = seller.team.name if seller and seller.team else (lead.team.name if lead.team else "")
        if seller and seller.role != RoleEnum.marketing_staff:
            seller_id = None
        rows.append({"item": lp, "lead": lead, "seller_id": seller_id,
                     "seller_name": seller_name if seller_id else "Unassigned",
                     "seller_team": seller_team if seller_id else ""})
    return rows


def _lead_rows(db: Session, leads):
    headers = ["ID", "Name", "Email", "Phone", "Company", "Source", "Place/Area", "Referred By", "Status",
               "Assigned To", "Team", "Created", "Converted"]
    rows = []
    for l in leads:
        rows.append([
            l.id, f"{l.first_name} {l.last_name or ''}".strip(), l.email or "", l.phone or "",
            l.company or "", l.source or "", l.place_area or "", l.referred_by or "", l.status.value,
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
                          subtitle=f"Generated {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", branding=_report_branding(db))
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
    staff_id: Optional[int] = None,
    source: Optional[str] = None,
    export: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = _visible_leads_query(db, current_user)
    base = _apply_common_filters(base, date_from, date_to, team_id, staff_id, source, None)
    all_leads = base.all()

    staff_q = db.query(User).filter(User.role == RoleEnum.marketing_staff)
    if current_user.role == RoleEnum.team_leader:
        staff_q = staff_q.filter(User.team_id == current_user.team_id)
    if team_id:
        staff_q = staff_q.filter(User.team_id == team_id)
    if staff_id:
        staff_q = staff_q.filter(User.id == staff_id)
    staff_list = staff_q.order_by(User.full_name).all()

    sales = _sales_rows(db, current_user, date_from, date_to, team_id, staff_id, source)
    interests = _product_interest_rows(db, current_user, date_from, date_to, team_id, staff_id, source)

    # Build one row per staff/product. This preserves product visibility even
    # when a product is only an interested/quoted item; Units Sold and Revenue
    # remain strictly conversion-based for incentive calculations.
    by_staff_product = {}
    for r in interests:
        lp, lead = r["item"], r["lead"]
        if not r["seller_id"]:
            continue
        product = lp.product
        key = (r["seller_id"], lp.product_id, product.name if product else "", product.sku if product else "")
        g = by_staff_product.setdefault(key, {"sold_units": 0, "revenue": 0, "sold_leads": set(), "dates": [], "converted_by": set(), "leads": set()})
        g["leads"].add(lead.id)

    for r in sales:
        item, conversion, lead = r["item"], r["conversion"], r["lead"]
        if not r["seller_id"]:
            continue
        key = (r["seller_id"], item.product_id, item.product_name, item.sku or "")
        g = by_staff_product.setdefault(key, {"sold_units": 0, "revenue": 0, "sold_leads": set(), "dates": [], "converted_by": set(), "leads": set()})
        g["sold_units"] += item.quantity
        g["revenue"] += item.line_total
        g["sold_leads"].add(lead.id)
        if conversion.conversion_date:
            g["dates"].append(conversion.conversion_date.strftime("%Y-%m-%d %H:%M"))
        if conversion.converted_by:
            g["converted_by"].add(conversion.converted_by.full_name)

    headers = ["Staff", "Team", "Total Leads", "New", "Follow-up", "Pending", "Converted", "Lost",
               "Conversion %", "Product", "SKU", "Units Sold", "Sales Revenue", "Conversion Date", "Lead ID", "Customer", "Converted By"]
    rows = []
    for staff in staff_list:
        leads = [l for l in all_leads if l.assigned_to_id == staff.id]
        total = len(leads)
        converted = sum(l.status == LeadStatusEnum.converted for l in leads)
        conv_pct = round((converted / total) * 100, 1) if total else 0.0
        staff_keys = [k for k in by_staff_product if k[0] == staff.id]
        if not staff_keys:
            rows.append([staff.full_name, staff.team.name if staff.team else "", total,
                         sum(l.status == LeadStatusEnum.new for l in leads),
                         sum(l.status == LeadStatusEnum.follow_up for l in leads),
                         sum(l.status == LeadStatusEnum.pending for l in leads), converted,
                         sum(l.status == LeadStatusEnum.lost for l in leads), conv_pct,
                         "", "", 0, 0, "", "", "", ""])
            continue
        for key in sorted(staff_keys, key=lambda k: (k[2].lower(), k[3].lower())):
            product_name, sku = key[2], key[3]
            g = by_staff_product[key]
            # For incentive detail, show the conversion-level date/customer
            # when there is a sale. Interest-only rows intentionally have no
            # conversion date and zero sales.
            sale_rows = [r for r in sales if r["seller_id"] == staff.id and r["item"].product_id == key[1]]
            if sale_rows:
                for r in sale_rows:
                    item, conversion, lead = r["item"], r["conversion"], r["lead"]
                    rows.append([staff.full_name, staff.team.name if staff.team else "", total,
                                 sum(l.status == LeadStatusEnum.new for l in leads),
                                 sum(l.status == LeadStatusEnum.follow_up for l in leads),
                                 sum(l.status == LeadStatusEnum.pending for l in leads), converted,
                                 sum(l.status == LeadStatusEnum.lost for l in leads), conv_pct,
                                 item.product_name, item.sku or "", item.quantity, item.line_total,
                                 conversion.conversion_date.strftime("%Y-%m-%d %H:%M") if conversion.conversion_date else "",
                                 lead.id, f"{lead.first_name} {lead.last_name or ''}".strip(),
                                 conversion.converted_by.full_name if conversion.converted_by else ""])
            else:
                rows.append([staff.full_name, staff.team.name if staff.team else "", total,
                             sum(l.status == LeadStatusEnum.new for l in leads),
                             sum(l.status == LeadStatusEnum.follow_up for l in leads),
                             sum(l.status == LeadStatusEnum.pending for l in leads), converted,
                             sum(l.status == LeadStatusEnum.lost for l in leads), conv_pct,
                             product_name, sku, 0, 0, "", "", "", ""])

    if export == "xlsx":
        data = build_xlsx(headers, rows, title="staff_performance")
        return StreamingResponse(iter([data]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=staff_performance.xlsx"})
    if export == "pdf":
        data = build_pdf(headers, rows, title="Staff Performance & Sales Report",
                         subtitle=f"Sales attributed to the lead's assigned marketing staff • Generated {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                         branding=_report_branding(db))
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
        data = build_pdf(headers, rows, title="Team Performance Report", branding=_report_branding(db))
        return StreamingResponse(iter([data]), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=team_performance.pdf"})

    return {"headers": headers, "rows": rows}


@router.get("/follow-ups")
def follow_up_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visible = _visible_leads_query(db, current_user).subquery()
    q = db.query(FollowUp, Lead, User).join(Lead, FollowUp.lead_id == Lead.id).outerjoin(User, FollowUp.staff_id == User.id).join(visible, Lead.id == visible.c.id)
    now = dt.datetime.utcnow()
    today_start = dt.datetime.combine(dt.date.today(), dt.time.min)
    tomorrow = today_start + dt.timedelta(days=1)
    rows = q.filter(FollowUp.scheduled_at.isnot(None)).order_by(FollowUp.scheduled_at.asc()).all()
    overdue, today, upcoming = [], [], []
    for fu, lead, staff in rows:
        item = {"id": fu.id, "lead_id": lead.id, "lead_name": f"{lead.first_name} {lead.last_name or ''}".strip(),
                "company": lead.company, "scheduled_at": fu.scheduled_at, "completed_at": fu.completed_at,
                "follow_up_type": fu.follow_up_type, "outcome": fu.outcome, "notes": fu.notes,
                "staff_name": staff.full_name if staff else None, "status": lead.status.value}
        if fu.completed_at:
            continue
        if fu.scheduled_at < now:
            overdue.append(item)
        elif fu.scheduled_at < tomorrow:
            today.append(item)
        else:
            upcoming.append(item)
    completed_today = q.filter(FollowUp.completed_at >= today_start, FollowUp.completed_at < tomorrow).count()
    return {"counts": {"overdue": len(overdue), "today": len(today), "upcoming": len(upcoming), "completed_today": completed_today},
            "overdue": overdue[:50], "today": today[:50], "upcoming": upcoming[:50]}


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


@router.post("/email")
def email_report(payload: ReportEmailRequest, request: Request,
                 current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Generate a report using the same visibility rules as exports and email it."""
    allowed_types = {"new", "follow_up", "pending", "converted", "lost", "closed", "all", "staff", "team", "products"}
    requested = {str(x).lower() for x in payload.attachments}
    if payload.report_type not in allowed_types:
        raise HTTPException(400, "Unsupported report type")
    if not requested or not requested.issubset({"pdf", "xlsx"}):
        raise HTTPException(400, "Attachments must be PDF and/or XLSX")
    if not payload.recipients:
        raise HTTPException(400, "At least one recipient is required")
    if payload.report_type == "products":
        sales = _sales_rows(db, current_user, payload.date_from, payload.date_to, payload.team_id, payload.staff_id, payload.source)
        groups = {}
        for r in sales:
            item, lead = r["item"], r["lead"]
            key = (item.product_id, item.product_name, item.sku or "", r["seller_id"], r["seller_name"], r["seller_username"], r["seller_team"])
            g = groups.setdefault(key, {"units": 0, "sold_leads": set(), "revenue": 0, "currency": ""})
            g["units"] += item.quantity; g["sold_leads"].add(lead.id)
            g["revenue"] += item.line_total
            if item.product and item.product.currency: g["currency"] = item.product.currency
        headers = ["Product", "SKU", "Sold By", "Team", "Converted Leads", "Units Sold", "Revenue", "Conversion Date Range"]
        rows = []
        for key, g in sorted(groups.items(), key=lambda x: (x[0][1].lower(), x[0][4].lower())):
            rows.append([key[1], key[2], key[4], key[6], len(g["sold_leads"]), g["units"], f'{g["currency"]} {g["revenue"]}'.strip(), f'{payload.date_from or "All"} to {payload.date_to or "All"}'])
        title = "Product Performance & Sales Attribution Report"
    elif payload.report_type == "staff":
        base = _apply_common_filters(_visible_leads_query(db, current_user), payload.date_from, payload.date_to, payload.team_id, payload.staff_id, payload.source, None)
        staff_q = db.query(User).filter(User.role == RoleEnum.marketing_staff)
        if current_user.role == RoleEnum.team_leader: staff_q = staff_q.filter(User.team_id == current_user.team_id)
        if payload.team_id: staff_q = staff_q.filter(User.team_id == payload.team_id)
        if payload.staff_id: staff_q = staff_q.filter(User.id == payload.staff_id)
        staff_list = staff_q.order_by(User.full_name).all()
        sales = _sales_rows(db, current_user, payload.date_from, payload.date_to, payload.team_id, payload.staff_id, payload.source)
        sales_by_staff = {}
        for r in sales: sales_by_staff.setdefault(r["seller_id"], []).append(r)
        headers = ["Staff", "Team", "Total Leads", "New", "Follow-up", "Pending", "Converted", "Lost", "Conversion %", "Product", "SKU", "Units Sold", "Sales Revenue", "Conversion Date", "Lead ID", "Customer", "Converted By"]
        rows = []
        all_leads = base.all()
        for staff in staff_list:
            leads = [l for l in all_leads if l.assigned_to_id == staff.id]
            total = len(leads); converted = sum(l.status == LeadStatusEnum.converted for l in leads); conv_pct = round(converted * 100 / total, 1) if total else 0.0
            staff_sales = sales_by_staff.get(staff.id, [])
            if not staff_sales:
                rows.append([staff.full_name, staff.team.name if staff.team else "", total, sum(l.status == LeadStatusEnum.new for l in leads), sum(l.status == LeadStatusEnum.follow_up for l in leads), sum(l.status == LeadStatusEnum.pending for l in leads), converted, sum(l.status == LeadStatusEnum.lost for l in leads), conv_pct, "", "", 0, 0, "", "", "", ""])
            else:
                for r in staff_sales:
                    item, conversion, lead = r["item"], r["conversion"], r["lead"]
                    rows.append([staff.full_name, staff.team.name if staff.team else "", total, sum(l.status == LeadStatusEnum.new for l in leads), sum(l.status == LeadStatusEnum.follow_up for l in leads), sum(l.status == LeadStatusEnum.pending for l in leads), converted, sum(l.status == LeadStatusEnum.lost for l in leads), conv_pct, item.product_name, item.sku or "", item.quantity, item.line_total, conversion.conversion_date.strftime("%Y-%m-%d %H:%M") if conversion.conversion_date else "", lead.id, f"{lead.first_name} {lead.last_name or ''}".strip(), conversion.converted_by.full_name if conversion.converted_by else ""])
        title = "Staff Performance & Sales Report"
    else:
        stage = "all" if payload.report_type == "all" else payload.report_type
        q = _visible_leads_query(db, current_user)
        status_filter = None if stage == "all" else LeadStatusEnum(stage)
        q = _apply_common_filters(q, payload.date_from, payload.date_to, payload.team_id,
                                  payload.staff_id, payload.source, status_filter)
        headers, rows = _lead_rows(db, q.order_by(Lead.created_at.desc()).all())
        title = f"Lead Report: {stage.replace('_', ' ').title()}"

    attachments = []
    if "xlsx" in requested:
        attachments.append(("leadcrm_report.xlsx", build_xlsx(headers, rows, title=title), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    if "pdf" in requested:
        attachments.append(("leadcrm_report.pdf", build_pdf(headers, rows, title=title,
                           subtitle=f"Generated {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", branding=_report_branding(db)), "application/pdf"))
    if not attachments:
        raise HTTPException(400, "Select PDF and/or XLSX attachment")
    try:
        send_email(db, payload.recipients, payload.subject or title,
                   payload.message or f"Please find the requested {title} attached.", attachments)
    except Exception as exc:
        log_action(db, current_user, "report_email_failed", "report", None, {"report_type": payload.report_type, "error": str(exc)}, request)
        raise HTTPException(400, f"Could not send report email: {exc}")
    log_action(db, current_user, "report_emailed", "report", None,
               {"report_type": payload.report_type, "recipients": payload.recipients, "attachments": sorted(requested)}, request)
    return {"detail": "Report emailed successfully"}


@router.get("/products")
def product_performance_report(
    date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None,
    team_id: Optional[int] = None, staff_id: Optional[int] = None, source: Optional[str] = None,
    export: Optional[str] = Query(None), current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)):
    sales = _sales_rows(db, current_user, date_from, date_to, team_id, staff_id, source)
    interests = _product_interest_rows(db, current_user, date_from, date_to, team_id, staff_id, source)

    # Include products attached to visible leads as well as products actually
    # sold. A product with no conversion remains clearly distinguishable by
    # zero Units Sold / Revenue, rather than disappearing from the report.
    groups = {}
    for r in interests:
        item = r["item"]
        product = item.product
        key = (item.product_id, product.name if product else "", product.sku if product else "",
               r["seller_id"], r["seller_name"], r["seller_team"])
        g = groups.setdefault(key, {"units": 0, "sold_leads": set(), "revenue": 0, "currency": ""})
        if product and product.currency:
            g["currency"] = product.currency

    for r in sales:
        item, lead = r["item"], r["lead"]
        key = (item.product_id, item.product_name, item.sku or "", r["seller_id"], r["seller_name"], r["seller_team"])
        g = groups.setdefault(key, {"units": 0, "sold_leads": set(), "revenue": 0, "currency": ""})
        g["units"] += item.quantity
        g["sold_leads"].add(lead.id)
        g["revenue"] += item.line_total
        if item.product and item.product.currency:
            g["currency"] = item.product.currency

    headers = ["Product", "SKU", "Sold By", "Team", "Converted Leads", "Units Sold", "Revenue", "Conversion Date Range"]
    rows = []
    for key, g in sorted(groups.items(), key=lambda x: (x[0][1].lower(), x[0][4].lower())):
        rows.append([key[1], key[2], key[4], key[5], len(g["sold_leads"]), g["units"],
                     f'{g["currency"]} {g["revenue"]}'.strip(),
                     f'{date_from or "All"} to {date_to or "All"}'])

    if export == "xlsx":
        data = build_xlsx(headers, rows, title="product_performance")
        return StreamingResponse(iter([data]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=product_performance.xlsx"})
    if export == "pdf":
        data = build_pdf(headers, rows, title="Product Performance & Sales Attribution Report",
                         subtitle=f"Generated {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", branding=_report_branding(db))
        return StreamingResponse(iter([data]), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=product_performance.pdf"})
    return {"headers": headers, "rows": rows}

