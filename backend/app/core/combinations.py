"""Logs oversize items packed using 2+ regular boxes taped together
(the weekend batch-entry workflow)."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import BoxCombination
from app.core.ledger import deduct_from_ledger


def log_combination_entry(db: Session, date: str, oversize_dims: str, brand_id: int,
                           qty_of_oversize_items: int, component_box_id: int,
                           component_qty_used: int, reference_invoice_no: str = None,
                           notes: str = None) -> dict:
    combo = BoxCombination(
        date=date, oversize_dims=oversize_dims, brand_id=brand_id,
        qty_of_oversize_items=qty_of_oversize_items,
        component_box_id=component_box_id, component_qty_used=component_qty_used,
        reference_invoice_no=reference_invoice_no, notes=notes,
    )
    db.add(combo)
    db.commit()
    db.refresh(combo)

    deduction = deduct_from_ledger(
        db, component_box_id, component_qty_used,
        reference_type="combination",
        reference_id=f"combo-{combo.id}",
        notes=f"Oversize {oversize_dims} packed with {component_qty_used}x component box",
    )

    # Track recurring usage on the box_type so we can flag it for catalog promotion
    box = combo.component_box
    box.times_used = (box.times_used or 0) + 1
    db.commit()

    return {"combination_id": combo.id, "deduction": deduction, "times_used": box.times_used}


def log_combinations_batch(db: Session, entries: list[dict]) -> list[dict]:
    return [log_combination_entry(db, **entry) for entry in entries]


def check_recurring_oversize_patterns(db: Session, min_occurrences: int = 3) -> list[dict]:
    """Flags oversize dims that have been logged often enough that the
    catalog itself should probably be expanded, instead of taping boxes."""
    rows = (
        db.query(BoxCombination.oversize_dims, func.count(BoxCombination.id).label("count"))
        .group_by(BoxCombination.oversize_dims)
        .having(func.count(BoxCombination.id) >= min_occurrences)
        .all()
    )
    return [{"oversize_dims": r[0], "occurrences": r[1]} for r in rows]
