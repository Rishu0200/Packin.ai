"""
Deterministic box-size resolution. No LLM involved here — this is pure
arithmetic against the catalog table, exactly as designed:

- Regular items: dims already match a catalog entry exactly.
- Outsize items: each axis rounds UP independently to the nearest available
  catalog value (e.g. 15x18x4 -> 15x20x4, since dim2's only catalog values
  are 16/18/20 and it needs the smallest one >= 18).
- Items exceeding the catalog max on any axis (e.g. dim1=23) cannot be
  resolved automatically -> needs_review.
"""
from sqlalchemy.orm import Session
from app.db.models import CatalogDimension


def get_catalog_values(db: Session, axis: str) -> list[int]:
    rows = (
        db.query(CatalogDimension)
        .filter(CatalogDimension.axis == axis, CatalogDimension.active == True)  # noqa: E712
        .order_by(CatalogDimension.value.asc())
        .all()
    )
    return [r.value for r in rows]


def round_to_catalog(value: int, catalog_values: list[int]) -> int | None:
    """Smallest catalog value >= value, or None if value exceeds the max."""
    valid = [v for v in catalog_values if v >= value]
    return min(valid) if valid else None


def resolve_box(db: Session, dim1: int, dim2: int, dim3: int) -> dict:
    """Returns one of:
    - {"status": "matched", "dim1":.., "dim2":.., "dim3":.., "was_outsize": bool}
    - {"status": "needs_review", "reason": "..."}
    """
    d1_catalog = get_catalog_values(db, "dim1")
    d2_catalog = get_catalog_values(db, "dim2")
    d3_catalog = get_catalog_values(db, "dim3")

    r1 = round_to_catalog(dim1, d1_catalog)
    r2 = round_to_catalog(dim2, d2_catalog)
    r3 = round_to_catalog(dim3, d3_catalog)

    if r1 is None or r2 is None or r3 is None:
        exceeded = []
        if r1 is None:
            exceeded.append(f"dim1={dim1} (max {max(d1_catalog) if d1_catalog else '?'})")
        if r2 is None:
            exceeded.append(f"dim2={dim2} (max {max(d2_catalog) if d2_catalog else '?'})")
        if r3 is None:
            exceeded.append(f"dim3={dim3} (max {max(d3_catalog) if d3_catalog else '?'})")
        return {
            "status": "needs_review",
            "reason": f"Exceeds catalog max on: {', '.join(exceeded)}",
        }

    was_outsize = (r1, r2, r3) != (dim1, dim2, dim3)
    return {"status": "matched", "dim1": r1, "dim2": r2, "dim3": r3, "was_outsize": was_outsize}
