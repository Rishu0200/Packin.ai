"""Monitors ledger stock levels and drafts reorder suggestions.
Never places an order automatically — always a draft for human approval."""
from sqlalchemy.orm import Session
from app.db.models import BoxType, Brand
from app.core.ledger import get_current_stock


def check_low_stock(db: Session) -> list[dict]:
    boxes = db.query(BoxType).all()
    low = []
    for box in boxes:
        stock = get_current_stock(db, box.id)
        if stock < box.reorder_threshold:
            brand = db.query(Brand).filter_by(id=box.brand_id).first()
            # Simple draft quantity: bring stock up to 2x the threshold.
            suggested_qty = max(box.reorder_threshold * 2 - stock, 1)
            low.append({
                "box_id": box.id,
                "size": box.size_label,
                "brand": brand.name if brand else "—",
                "current_stock": stock,
                "threshold": box.reorder_threshold,
                "suggested_reorder_qty": suggested_qty,
            })
    return low
