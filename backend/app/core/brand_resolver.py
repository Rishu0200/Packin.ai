"""Resolves which brand a shipment belongs to, via the customer mapping.
Brand is tied to the customer, per the confirmed business rule — no fuzzy
text parsing needed here."""
import re
from sqlalchemy.orm import Session
from app.db.models import CustomerBrandMap, Brand


def normalize_customer_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s]", "", name)
    return name


def resolve_brand(db: Session, customer_name: str) -> dict:
    normalized = normalize_customer_name(customer_name)
    mapping = db.query(CustomerBrandMap).filter_by(customer_name=normalized).first()
    if not mapping:
        return {"status": "unmapped_customer", "customer": customer_name}
    brand = db.query(Brand).filter_by(id=mapping.brand_id).first()
    return {"status": "mapped", "brand_id": brand.id, "brand_name": brand.name}


def map_customer_to_brand(db: Session, customer_name: str, brand_id: int) -> CustomerBrandMap:
    normalized = normalize_customer_name(customer_name)
    existing = db.query(CustomerBrandMap).filter_by(customer_name=normalized).first()
    if existing:
        existing.brand_id = brand_id
        db.commit()
        return existing
    mapping = CustomerBrandMap(customer_name=normalized, brand_id=brand_id)
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping
