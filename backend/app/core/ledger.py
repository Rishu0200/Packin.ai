"""
The ledger is append-only and is the real source of truth for stock.
Every function here either writes a ledger entry or explicitly refuses to,
returning a reason instead. Nothing silently fails.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import BoxLedger, BoxType, Brand
from app.config import LARGE_DEDUCTION_PCT_THRESHOLD


def get_or_create_box_type(db: Session, dim1: int, dim2: int, dim3: int,
                            brand_id: int, is_custom: bool = False) -> tuple[BoxType, bool]:
    """Returns (box_type, was_created). New box types start at zero stock —
    the negative-stock guard then naturally forces a review before anything
    can be deducted from them, which is exactly right for a brand-new size."""
    box = (
        db.query(BoxType)
        .filter_by(dim1=dim1, dim2=dim2, dim3=dim3, brand_id=brand_id)
        .first()
    )
    if box:
        return box, False
    box = BoxType(dim1=dim1, dim2=dim2, dim3=dim3, brand_id=brand_id,
                   current_stock=0, is_custom=is_custom)
    db.add(box)
    db.commit()
    db.refresh(box)
    return box, True


def get_current_stock(db: Session, box_id: int) -> int:
    """Recomputes stock from the ledger — the authoritative value."""
    total = (
        db.query(func.coalesce(func.sum(BoxLedger.qty_change), 0))
        .filter(BoxLedger.box_id == box_id)
        .scalar()
    )
    return int(total)


def is_already_processed(db: Session, reference_type: str, reference_id: str) -> bool:
    """Idempotency check — prevents double-processing the same invoice/PO."""
    existing = (
        db.query(BoxLedger)
        .filter_by(reference_type=reference_type, reference_id=reference_id)
        .first()
    )
    return existing is not None


def write_ledger_entry(db: Session, box_id: int, qty_change: int,
                        reference_type: str, reference_id: str, notes: str = None, created_by: str = None) -> BoxLedger:
    entry = BoxLedger(
        box_id=box_id, qty_change=qty_change,
        reference_type=reference_type, reference_id=reference_id, notes=notes,
        created_by=created_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Recompute the cached stock value straight from the ledger so it can
    # never drift from the source of truth.
    box = db.query(BoxType).filter_by(id=box_id).first()
    box.current_stock = get_current_stock(db, box_id)
    db.commit()
    return entry


def deduct_from_ledger(db: Session, box_id: int, qty: float,
                        reference_type: str, reference_id: str, notes: str = None, created_by: str = None) -> dict:
    """The core guardrail: never let a deduction push stock negative, and
    flag unusually large deductions relative to current stock (catches
    extraction errors like qty=500 instead of qty=5)."""
    qty = int(round(qty))
    box = db.query(BoxType).filter_by(id=box_id).first()
    current = get_current_stock(db, box_id)

    if qty > current:
        return {
            "status": "needs_review",
            "reason": f"Insufficient stock: have {current}, need {qty}",
            "box_id": box_id, "shortage": qty - current,
        }

    if current > 0 and (qty / current) > LARGE_DEDUCTION_PCT_THRESHOLD:
        return {
            "status": "needs_review",
            "reason": f"Deduction of {qty} is >{int(LARGE_DEDUCTION_PCT_THRESHOLD*100)}% "
                      f"of current stock ({current}) — possible extraction error",
            "box_id": box_id,
        }

    write_ledger_entry(db, box_id, -qty, reference_type, reference_id, notes, created_by)
    return {"status": "deducted", "box_id": box_id, "qty": qty, "remaining": current - qty}


def add_to_ledger(db: Session, box_id: int, qty: float,
                   reference_type: str, reference_id: str, notes: str = None, created_by: str = None) -> dict:
    qty = int(round(qty))
    write_ledger_entry(db, box_id, qty, reference_type, reference_id, notes, created_by)
    new_total = get_current_stock(db, box_id)
    return {"status": "added", "box_id": box_id, "qty": qty, "new_total": new_total}


def find_brands_with_stock(db: Session, dim1: int, dim2: int, dim3: int,
                            exclude_brand_id: int, min_qty: int) -> list[dict]:
    """Used by the substitution flow: which other brands could cover this
    shortage at the same box size?"""
    candidates = (
        db.query(BoxType)
        .filter(BoxType.dim1 == dim1, BoxType.dim2 == dim2, BoxType.dim3 == dim3,
                BoxType.brand_id != exclude_brand_id)
        .all()
    )
    results = []
    for box in candidates:
        stock = get_current_stock(db, box.id)
        if stock >= min_qty:
            brand = db.query(Brand).filter_by(id=box.brand_id).first()
            results.append({"box_id": box.id, "brand_id": brand.id,
                             "brand_name": brand.name, "available_stock": stock})
    return results
