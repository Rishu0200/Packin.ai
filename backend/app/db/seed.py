"""Seeds the catalog dimensions and brand master data.
Safe to re-run — skips anything that already exists."""
from app.db.session import SessionLocal, init_db
from app.db.models import CatalogDimension, Brand, CustomerBrandMap

CATALOG = {
    "dim1": [15, 17, 19, 21],
    "dim2": [20],
    "dim3": [4, 6, 8],
}

BRANDS = ["Metro Steel", "Modular Kitchen", "Danfe", "Dream Kitchen"]

# Sample customer -> brand mapping (edit/extend via the /brands API in practice)
SAMPLE_CUSTOMER_MAP = {
    "shree ganesh plywood": "Metro Steel",
}


def seed():
    init_db()
    db = SessionLocal()
    try:
        for axis, values in CATALOG.items():
            for v in values:
                exists = db.query(CatalogDimension).filter_by(axis=axis, value=v).first()
                if not exists:
                    db.add(CatalogDimension(axis=axis, value=v, active=True))

        brand_objs = {}
        for name in BRANDS:
            b = db.query(Brand).filter_by(name=name).first()
            if not b:
                b = Brand(name=name, active=True)
                db.add(b)
                db.flush()
            brand_objs[name] = b

        for customer, brand_name in SAMPLE_CUSTOMER_MAP.items():
            exists = db.query(CustomerBrandMap).filter_by(customer_name=customer).first()
            if not exists:
                db.add(CustomerBrandMap(customer_name=customer, brand_id=brand_objs[brand_name].id))

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
