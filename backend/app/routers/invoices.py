from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Invoice, InvoiceLineItem
from app.agents.extraction_agent import extract_invoice
from app.core.resolver import resolve_box
from app.core.brand_resolver import resolve_brand
from app.core.substitution import deduct_with_substitution_check
from app.core.ledger import get_or_create_box_type, is_already_processed
from app.core.notifications import notify_low_stock_if_any

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/upload")
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_bytes = await file.read()
    media_type = file.content_type or "application/pdf"

    extracted = extract_invoice(file_bytes, media_type=media_type)
    if "error" in extracted:
        raise HTTPException(status_code=422, detail=extracted)

    invoice_no = extracted.get("invoice_no", "UNKNOWN")

    if db.query(Invoice).filter_by(invoice_no=invoice_no).first():
        return {"status": "skipped", "reason": "duplicate invoice_no", "invoice_no": invoice_no}

    invoice = Invoice(invoice_no=invoice_no, date=extracted.get("date"),
                       party=extracted.get("party"))
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    brand_result = resolve_brand(db, extracted.get("party", ""))

    results = []
    for item in extracted.get("line_items", []):
        li = InvoiceLineItem(
            invoice_id=invoice.id,
            raw_description=item.get("raw_description"),
            dim1=item.get("dim1"), dim2=item.get("dim2"), dim3=item.get("dim3"),
            product_type=item.get("product_type"),
            qty=item.get("qty"),
        )

        if item.get("unparsed") or item.get("dim1") is None:
            li.status = "unparsed"
            db.add(li)
            db.commit()
            results.append({"line_item_id": li.id, "status": "unparsed"})
            continue

        if brand_result["status"] != "mapped":
            li.status = "unmapped_customer"
            li.reason = f"Customer '{extracted.get('party')}' has no brand mapping"
            db.add(li)
            db.commit()
            results.append({"line_item_id": li.id, "status": "unmapped_customer"})
            continue

        resolved = resolve_box(db, item["dim1"], item["dim2"], item["dim3"])
        if resolved["status"] == "needs_review":
            li.status = "needs_review"
            li.reason = resolved["reason"]
            db.add(li)
            db.commit()
            results.append({"line_item_id": li.id, "status": "needs_review",
                             "reason": resolved["reason"]})
            continue

        box, _created = get_or_create_box_type(
            db, resolved["dim1"], resolved["dim2"], resolved["dim3"], brand_result["brand_id"]
        )
        li.resolved_box_id = box.id

        deduction = deduct_with_substitution_check(
            db, box.id, resolved["dim1"], resolved["dim2"], resolved["dim3"],
            brand_result["brand_id"], item["qty"],
            reference_type="invoice", reference_id=invoice_no,
        )

        li.status = deduction["status"]
        db.add(li)
        db.commit()
        results.append({"line_item_id": li.id, **deduction})

    notify_low_stock_if_any(db, trigger=f"invoice {invoice_no} upload")
    return {"invoice_no": invoice_no, "line_item_results": results}
