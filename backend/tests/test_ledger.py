import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Brand
from app.core.ledger import (
    get_or_create_box_type, add_to_ledger, deduct_from_ledger,
    get_current_stock, is_already_processed,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    brand = Brand(name="Metro Steel", active=True)
    session.add(brand)
    session.commit()
    yield session
    session.close()


def test_new_box_type_starts_at_zero_stock(db_session):
    brand = db_session.query(Brand).first()
    box, created = get_or_create_box_type(db_session, 15, 20, 4, brand.id)
    assert created is True
    assert get_current_stock(db_session, box.id) == 0


def test_add_then_deduct_updates_stock_correctly(db_session):
    brand = db_session.query(Brand).first()
    box, _ = get_or_create_box_type(db_session, 15, 20, 4, brand.id)
    add_to_ledger(db_session, box.id, 100, "po", "PO-001")
    assert get_current_stock(db_session, box.id) == 100

    result = deduct_from_ledger(db_session, box.id, 30, "invoice", "INV-001")
    assert result["status"] == "deducted"
    assert get_current_stock(db_session, box.id) == 70


def test_deduction_exceeding_stock_is_flagged_not_applied(db_session):
    brand = db_session.query(Brand).first()
    box, _ = get_or_create_box_type(db_session, 15, 20, 4, brand.id)
    add_to_ledger(db_session, box.id, 10, "po", "PO-002")

    result = deduct_from_ledger(db_session, box.id, 50, "invoice", "INV-002")
    assert result["status"] == "needs_review"
    # Stock must be unchanged — the deduction was never applied
    assert get_current_stock(db_session, box.id) == 10


def test_large_deduction_relative_to_stock_is_flagged(db_session):
    brand = db_session.query(Brand).first()
    box, _ = get_or_create_box_type(db_session, 15, 20, 4, brand.id)
    add_to_ledger(db_session, box.id, 100, "po", "PO-003")

    # 60% of stock in one shot should trip the >50% sanity threshold
    result = deduct_from_ledger(db_session, box.id, 60, "invoice", "INV-003")
    assert result["status"] == "needs_review"
    assert get_current_stock(db_session, box.id) == 100


def test_idempotency_prevents_duplicate_invoice_processing(db_session):
    brand = db_session.query(Brand).first()
    box, _ = get_or_create_box_type(db_session, 15, 20, 4, brand.id)
    add_to_ledger(db_session, box.id, 100, "po", "PO-004")
    deduct_from_ledger(db_session, box.id, 10, "invoice", "INV-004")

    assert is_already_processed(db_session, "invoice", "INV-004") is True
    assert is_already_processed(db_session, "invoice", "INV-999") is False
