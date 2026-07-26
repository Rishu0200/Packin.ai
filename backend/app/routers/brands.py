from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Brand, CustomerBrandMap
from app.core.brand_resolver import map_customer_to_brand
from app.schemas import BrandCreate, CustomerMapRequest

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("")
def list_brands(db: Session = Depends(get_db)):
    brands = db.query(Brand).all()
    return {"brands": [{"id": b.id, "name": b.name, "active": b.active} for b in brands]}


@router.post("")
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    existing = db.query(Brand).filter_by(name=payload.name).first()
    if existing:
        return {"id": existing.id, "name": existing.name, "status": "already_exists"}
    brand = Brand(name=payload.name, active=True)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return {"id": brand.id, "name": brand.name, "status": "created"}


@router.post("/map-customer")
def map_customer(payload: CustomerMapRequest, db: Session = Depends(get_db)):
    mapping = map_customer_to_brand(db, payload.customer_name, payload.brand_id)
    return {"customer_name": mapping.customer_name, "brand_id": mapping.brand_id}


@router.get("/customer-map")
def list_customer_map(db: Session = Depends(get_db)):
    rows = db.query(CustomerBrandMap).all()
    return {"mappings": [{"customer_name": r.customer_name, "brand_id": r.brand_id}
                          for r in rows]}
