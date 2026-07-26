from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import InvoiceLineItem
from app.core.substitution import apply_substitution, correct_brand_used
from app.core.brand_resolver import map_customer_to_brand
from app.schemas import SubstitutionConfirm, BrandCorrection, CustomerMapRequest

router = APIRouter(prefix="/review", tags=["review_queue"])

FLAGGED_STATUSES = ["unparsed", "needs_review", "needs_substitution_confirm",
                    "unmapped_customer"]


@router.get("")
def list_review_queue(db: Session = Depends(get_db)):
    items = (
        db.query(InvoiceLineItem)
        .filter(InvoiceLineItem.status.in_(FLAGGED_STATUSES))
        .all()
    )
    return {"queue": [
        {
            "id": i.id, "invoice_id": i.invoice_id, "raw_description": i.raw_description,
            "dim1": i.dim1, "dim2": i.dim2, "dim3": i.dim3, "qty": i.qty,
            "status": i.status, "reason": i.reason,
        } for i in items
    ]}


@router.post("/resolve-substitution")
def resolve_substitution(payload: SubstitutionConfirm, db: Session = Depends(get_db)):
    li = db.query(InvoiceLineItem).filter_by(id=payload.line_item_id).first()
    if not li:
        raise HTTPException(status_code=404, detail="line item not found")

    result = apply_substitution(db, payload.chosen_box_id, li.qty,
                                 reference_type="invoice", reference_id=str(li.invoice_id))
    li.status = result["status"]
    li.resolved_box_id = payload.chosen_box_id
    db.commit()
    return result


@router.post("/correct-brand")
def correct_brand(payload: BrandCorrection, db: Session = Depends(get_db)):
    return correct_brand_used(db, payload.original_box_id, payload.corrected_box_id,
                               payload.qty, payload.reference_id, payload.notes)


@router.post("/map-unmapped-customer")
def map_unmapped_customer(payload: CustomerMapRequest, db: Session = Depends(get_db)):
    mapping = map_customer_to_brand(db, payload.customer_name, payload.brand_id)
    return {"status": "mapped", "customer_name": mapping.customer_name,
            "brand_id": mapping.brand_id}
