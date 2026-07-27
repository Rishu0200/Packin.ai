"""
Turns the raw append-only box_ledger into a human-readable activity feed —
answers "what changed, when, and why" without anyone having to query raw
ledger rows by hand.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import BoxLedger, BoxType, Brand

router = APIRouter(prefix="/activity", tags=["activity"])

REFERENCE_LABELS = {
    "invoice": "Invoice",
    "po": "Purchase order",
    "combination": "Oversize combination",
    "correction": "Manual correction",
}


@router.get("")
def list_activity(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    entries = (
        db.query(BoxLedger)
        .order_by(BoxLedger.timestamp.desc())
        .limit(limit)
        .all()
    )

    feed = []
    for e in entries:
        box = db.query(BoxType).filter_by(id=e.box_id).first()
        brand = db.query(Brand).filter_by(id=box.brand_id).first() if box else None
        direction = "added" if e.qty_change > 0 else "deducted"

        feed.append({
            "timestamp": e.timestamp.isoformat(),
            "type": REFERENCE_LABELS.get(e.reference_type, e.reference_type),
            "reference_id": e.reference_id,
            "box_size": box.size_label if box else "unknown",
            "brand": brand.name if brand else "unknown",
            "qty_change": e.qty_change,
            "direction": direction,
            "created_by": e.created_by or "system",
            "notes": e.notes,
            "summary": f"{REFERENCE_LABELS.get(e.reference_type, e.reference_type)} "
                       f"{e.reference_id} {direction} {abs(e.qty_change)} x "
                       f"{box.size_label if box else '?'} "
                       f"({brand.name if brand else '?'})"
                       f"{' — by ' + e.created_by if e.created_by else ''}",
        })
    return {"activity": feed}


@router.get("/summary")
def activity_summary(db: Session = Depends(get_db)):
    """Quick health signal: how much of what's flowing through the system
    is clean vs. needing review — the number worth watching over time."""
    from app.db.models import InvoiceLineItem

    total = db.query(InvoiceLineItem).count()
    flagged = (
        db.query(InvoiceLineItem)
        .filter(InvoiceLineItem.status.in_(
            ["unparsed", "needs_review", "needs_substitution_confirm", "unmapped_customer"]
        ))
        .count()
    )
    flag_rate = round((flagged / total) * 100, 1) if total else 0.0
    return {
        "total_line_items_processed": total,
        "currently_flagged": flagged,
        "flag_rate_pct": flag_rate,
    }
