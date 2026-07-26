import io
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import PurchaseOrder, Brand
from app.core.ledger import get_or_create_box_type, add_to_ledger, is_already_processed
from app.core.resolver import get_catalog_values
from app.agents.po_extraction_agent import extract_po_slip, validate_po_item

router = APIRouter(prefix="/po", tags=["purchase_orders"])


@router.post("/upload-excel")
async def upload_po_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Primary PO ingestion path — the structured PO_Upload_Template.xlsx
    filled in by supply chain ops. No LLM needed since the data is already
    structured; each row is validated against the catalog directly."""
    contents = await file.read()
    df = pd.read_excel(io.BytesIO(contents), sheet_name="PO_Entries", header=3)
    df = df.dropna(how="all")

    results = []
    for _, row in df.iterrows():
        po_ref = str(row.get("PO Reference No.", "")).strip()
        if not po_ref or po_ref.lower() == "nan":
            continue

        if is_already_processed(db, "po", po_ref) or \
                db.query(PurchaseOrder).filter_by(po_reference=po_ref).first():
            results.append({"po_reference": po_ref, "status": "skipped_duplicate"})
            continue

        brand_name = str(row.get("Brand", "")).strip()
        brand = db.query(Brand).filter_by(name=brand_name).first()

        dim1, dim2, dim3 = row.get("Dim 1"), row.get("Dim 2"), row.get("Dim 3")
        qty = row.get("Quantity Ordered")

        if not brand or pd.isna(dim1) or pd.isna(dim2) or pd.isna(dim3) or pd.isna(qty):
            results.append({
                "po_reference": po_ref, "status": "needs_review",
                "reason": "Missing brand/dimensions — likely a custom size described in Remarks",
                "remarks": row.get("Remarks"),
            })
            continue

        box, _created = get_or_create_box_type(db, int(dim1), int(dim2), int(dim3), brand.id)
        result = add_to_ledger(db, box.id, float(qty), reference_type="po", reference_id=po_ref)

        po = PurchaseOrder(po_reference=po_ref, date=str(row.get("PO Date")),
                            box_id=box.id, qty_added=int(qty),
                            vendor=str(row.get("Vendor / Supplier")), source="excel",
                            status="applied")
        db.add(po)
        db.commit()

        results.append({"po_reference": po_ref, "status": "applied", **result})

    return {"results": results}


@router.post("/upload-slip")
async def upload_po_slip(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Fallback path for handwritten slips. Extracts and validates but does
    NOT write to the ledger — handwriting risk means every slip requires
    explicit human confirmation via /po/confirm."""
    image_bytes = await file.read()
    media_type = file.content_type or "image/jpeg"

    dim1_values = get_catalog_values(db, "dim1")
    dim2_values = get_catalog_values(db, "dim2")
    dim3_values = get_catalog_values(db, "dim3")
    brand_names = [b.name for b in db.query(Brand).filter_by(active=True).all()]

    extracted = extract_po_slip(image_bytes, media_type, dim1_values, dim2_values,
                                 dim3_values, brand_names)
    if "error" in extracted:
        raise HTTPException(status_code=422, detail=extracted)

    validated_items = []
    for item in extracted.get("items", []):
        validation = validate_po_item(item, dim1_values, dim2_values, dim3_values)
        validated_items.append({**item, **validation})

    return {"items": validated_items, "note": "Nothing written to ledger yet — call "
                                                "/po/confirm with the reviewed items."}


@router.post("/confirm")
async def confirm_po_slip(po_reference: str, items: list[dict], db: Session = Depends(get_db)):
    """Applies a human-confirmed set of PO slip items to the ledger."""
    if is_already_processed(db, "po", po_reference):
        return {"status": "skipped_duplicate", "po_reference": po_reference}

    results = []
    for item in items:
        brand = db.query(Brand).filter_by(name=item["brand"]).first()
        if not brand:
            results.append({"status": "error", "reason": f"Unknown brand {item['brand']}"})
            continue
        box, _created = get_or_create_box_type(db, item["dim1"], item["dim2"], item["dim3"],
                                                 brand.id)
        result = add_to_ledger(db, box.id, item["qty"], reference_type="po",
                                reference_id=po_reference)
        po = PurchaseOrder(po_reference=po_reference, box_id=box.id, qty_added=item["qty"],
                            source="scanned_slip", status="applied")
        db.add(po)
        db.commit()
        results.append(result)

    return {"po_reference": po_reference, "results": results}
