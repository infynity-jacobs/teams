import io
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
import openpyxl

from app.database import get_db
from app.models import User, Lead, ImportBatch, LeadStatusHistory, LeadStatusEnum, Product, LeadProduct
from app.schemas import ImportResultOut
from app.deps import get_current_user, require_roles, log_action, LEADERS_UP
from app.routers.leads import _dedup_key

router = APIRouter(prefix="/api/import", tags=["import"])

# Fields the application understands for mapping
APPLICATION_FIELDS = [
    "first_name", "last_name", "email", "phone", "company", "source",
    "place_area", "referred_by", "products", "notes",
]
REQUIRED_FIELDS = ["first_name"]


def _read_workbook(file_bytes: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    data_rows = rows[1:]
    return headers, data_rows


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(*LEADERS_UP)),
):
    """Return detected column headers + first few sample rows so the UI can build a mapping form."""
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Only .xlsx/.xlsm files are supported")
    content = await file.read()
    headers, data_rows = _read_workbook(content)
    if not headers:
        raise HTTPException(400, "The uploaded file appears to be empty")
    sample = [list(r) for r in data_rows[:5]]
    return {
        "headers": headers,
        "sample_rows": sample,
        "row_count": len(data_rows),
        "application_fields": APPLICATION_FIELDS,
        "required_fields": REQUIRED_FIELDS,
    }


@router.post("/commit", response_model=ImportResultOut)
async def commit_import(
    request: Request,
    file: UploadFile = File(...),
    mapping: str = Form(..., description="JSON object: application_field -> excel_column_header"),
    default_team_id: int = Form(None),
    default_assigned_to_id: int = Form(None),
    default_source: str = Form(None),
    current_user: User = Depends(require_roles(*LEADERS_UP)),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Only .xlsx/.xlsm files are supported")
    try:
        field_map = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(400, "mapping must be valid JSON")

    for req in REQUIRED_FIELDS:
        if req not in field_map:
            raise HTTPException(400, f"Mapping must include the required field '{req}'")

    content = await file.read()
    headers, data_rows = _read_workbook(content)
    if not headers:
        raise HTTPException(400, "The uploaded file appears to be empty")

    header_index = {h: i for i, h in enumerate(headers)}
    for app_field, excel_col in field_map.items():
        if excel_col not in header_index:
            raise HTTPException(400, f"Column '{excel_col}' not found in file headers")

    # Team leaders may only import into their own team
    if current_user.role.value == "team_leader":
        default_team_id = current_user.team_id

    success, duplicate, errors = 0, 0, []
    seen_keys_this_batch = set()

    for row_num, row in enumerate(data_rows, start=2):  # row 1 is header
        try:
            values = {}
            for app_field, excel_col in field_map.items():
                idx = header_index[excel_col]
                cell = row[idx] if idx < len(row) else None
                values[app_field] = str(cell).strip() if cell is not None else None

            if not values.get("first_name"):
                errors.append({"row": row_num, "error": "Missing required field 'first_name'"})
                continue

            email = values.get("email")
            phone = values.get("phone")
            dedup = _dedup_key(email, phone)

            if dedup:
                if dedup in seen_keys_this_batch:
                    duplicate += 1
                    continue
                existing = db.query(Lead).filter(Lead.dedup_key == dedup).first()
                if existing:
                    duplicate += 1
                    continue
                seen_keys_this_batch.add(dedup)

            lead = Lead(
                first_name=values.get("first_name"),
                last_name=values.get("last_name"),
                email=email,
                phone=phone,
                company=values.get("company"),
                source=values.get("source") or default_source,
                place_area=values.get("place_area"),
                referred_by=values.get("referred_by"),
                notes=values.get("notes"),
                status=LeadStatusEnum.new,
                dedup_key=dedup,
                assigned_to_id=default_assigned_to_id,
                team_id=default_team_id,
                created_by_id=current_user.id,
            )
            db.add(lead)
            db.flush()
            product_text = values.get("products") or ""
            if product_text:
                names = [x.strip() for x in product_text.split(",") if x.strip()]
                for name in names:
                    product = db.query(Product).filter(Product.name.ilike(name), Product.is_active == True).first()
                    if not product:
                        raise ValueError(f"Unknown active product '{name}'")
                    db.add(LeadProduct(lead_id=lead.id, product_id=product.id, quantity=1, interest_status="interested"))
            db.add(LeadStatusHistory(lead_id=lead.id, old_status=None, new_status="new",
                                      changed_by_id=current_user.id, note=f"Imported (row {row_num})"))
            success += 1
        except Exception as exc:  # keep importing remaining rows on a per-row failure
            errors.append({"row": row_num, "error": str(exc)})

    batch = ImportBatch(
        filename=file.filename,
        imported_by_id=current_user.id,
        column_mapping=field_map,
        total_rows=len(data_rows),
        success_count=success,
        duplicate_count=duplicate,
        error_count=len(errors),
        error_detail=errors[:200],  # cap stored error detail
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    log_action(db, current_user, "import_leads", "import_batch", batch.id,
               {"success": success, "duplicate": duplicate, "errors": len(errors)}, request)

    return ImportResultOut(
        batch_id=batch.id, total_rows=batch.total_rows, success_count=success,
        duplicate_count=duplicate, error_count=len(errors), errors=errors[:50],
    )


@router.get("/batches")
def list_batches(
    current_user: User = Depends(require_roles(*LEADERS_UP)),
    db: Session = Depends(get_db),
):
    batches = db.query(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(50).all()
    return [
        {
            "id": b.id, "filename": b.filename, "total_rows": b.total_rows,
            "success_count": b.success_count, "duplicate_count": b.duplicate_count,
            "error_count": b.error_count, "created_at": b.created_at,
            "imported_by": b.imported_by.full_name if b.imported_by else None,
        }
        for b in batches
    ]
