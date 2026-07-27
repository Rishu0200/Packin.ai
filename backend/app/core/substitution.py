"""
Handles the case where the billed brand is out of stock and a different
brand's box was (or should be) used instead. This reuses the ledger's
insufficient-stock guard as the detection trigger, then surfaces
alternatives with real stock instead of just failing.
"""
from sqlalchemy.orm import Session
from app.core.ledger import get_current_stock, deduct_from_ledger, find_brands_with_stock


def deduct_with_substitution_check(db: Session, box_id: int, dim1: int, dim2: int, dim3: int,
                                    brand_id: int, qty: float,
                                    reference_type: str, reference_id: str, created_by: str = None) -> dict:
    qty_int = int(round(qty))
    current = get_current_stock(db, box_id)

    if current >= qty_int:
        return deduct_from_ledger(db, box_id, qty, reference_type, reference_id, created_by=created_by)

    alternatives = find_brands_with_stock(db, dim1, dim2, dim3, exclude_brand_id=brand_id,
                                           min_qty=qty_int)
    return {
        "status": "needs_substitution_confirm",
        "billed_box_id": box_id,
        "billed_brand_id": brand_id,
        "shortage": qty_int - current,
        "qty_needed": qty_int,
        "available_on_billed_brand": current,
        "suggested_alternatives": alternatives,
    }


def apply_substitution(db: Session, chosen_box_id: int, qty: float,
                        reference_type: str, reference_id: str, notes: str = None, created_by: str = None) -> dict:
    """Called once the admin picks which brand's box was actually used."""
    return deduct_from_ledger(db, chosen_box_id, qty, reference_type, reference_id,
                               notes=notes or "Substituted brand — confirmed by admin")


def correct_brand_used(db, original_box_id: int, corrected_box_id: int, qty: float,
                        reference_id: str, notes: str = None, created_by: str = None) -> dict:
    """Retroactive fix: reverse the original deduction, apply to the correct
    brand's box, keeping the full audit trail (both entries stay visible)."""
    from app.core.ledger import add_to_ledger  # local import avoids a cycle

    reverse = add_to_ledger(db, original_box_id, qty, "correction",
                             f"{reference_id}-reverse",
                             notes=notes or "Reversed — wrong brand originally recorded")
    apply = deduct_from_ledger(db, corrected_box_id, qty, "correction",
                                f"{reference_id}-corrected",
                                notes=notes or "Corrected to actual brand used")
    return {"reversed": reverse, "corrected": apply}
