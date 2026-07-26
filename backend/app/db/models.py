"""
PackIn.ai — database models.

Design principle: box_ledger is append-only and is the real source of truth
for stock. box_types.current_stock is a cached value kept in sync by the
ledger-writing functions in core/ledger.py, but can always be recomputed
from SUM(box_ledger.qty_change) for a given box_id.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class CatalogDimension(Base):
    """Editable master list of valid box dimensions per axis.
    Kept in the DB (not hardcoded) so 'promoting' a recurring custom size
    to the standard catalog is a data change, not a code deploy."""
    __tablename__ = "catalog_dimensions"

    id = Column(Integer, primary_key=True)
    axis = Column(String, nullable=False)   # "dim1" | "dim2" | "dim3"
    value = Column(Integer, nullable=False)
    active = Column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("axis", "value", name="uq_axis_value"),)


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    box_types = relationship("BoxType", back_populates="brand")


class CustomerBrandMap(Base):
    """Which brand a given customer always orders under."""
    __tablename__ = "customer_brand_map"

    id = Column(Integer, primary_key=True)
    customer_name = Column(String, nullable=False, unique=True)  # normalized, lowercase
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    brand = relationship("Brand")


class BoxType(Base):
    """One row per (size x brand) stock line."""
    __tablename__ = "box_types"

    id = Column(Integer, primary_key=True)
    dim1 = Column(Integer, nullable=False)
    dim2 = Column(Integer, nullable=False)
    dim3 = Column(Integer, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    current_stock = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=20)
    is_custom = Column(Boolean, default=False)
    times_used = Column(Integer, default=0)  # tracks recurring custom-size usage
    created_at = Column(DateTime, default=datetime.utcnow)

    brand = relationship("Brand", back_populates="box_types")

    __table_args__ = (
        UniqueConstraint("dim1", "dim2", "dim3", "brand_id", name="uq_box_size_brand"),
    )

    @property
    def size_label(self):
        return f"{self.dim1}x{self.dim2}x{self.dim3}"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_no = Column(String, nullable=False, unique=True)
    date = Column(String)
    party = Column(String)
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    line_items = relationship("InvoiceLineItem", back_populates="invoice")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    raw_description = Column(String)
    dim1 = Column(Integer, nullable=True)
    dim2 = Column(Integer, nullable=True)
    dim3 = Column(Integer, nullable=True)
    product_type = Column(String, nullable=True)  # THALI/PLATE/MP/BPO/S_C/C_S
    qty = Column(Float)
    resolved_box_id = Column(Integer, ForeignKey("box_types.id"), nullable=True)
    status = Column(String, default="pending")
    # pending | deducted | needs_review | needs_substitution | unparsed | unmapped_customer
    reason = Column(String, nullable=True)

    invoice = relationship("Invoice", back_populates="line_items")
    resolved_box = relationship("BoxType")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    po_reference = Column(String, nullable=False, unique=True)
    date = Column(String)
    box_id = Column(Integer, ForeignKey("box_types.id"), nullable=False)
    qty_added = Column(Integer)
    vendor = Column(String, nullable=True)
    source = Column(String, default="excel")  # excel | scanned_slip | manual
    status = Column(String, default="applied")  # applied | needs_review
    created_at = Column(DateTime, default=datetime.utcnow)

    box = relationship("BoxType")


class BoxCombination(Base):
    """Logs an oversize item packed using 2+ regular boxes taped together."""
    __tablename__ = "box_combinations"

    id = Column(Integer, primary_key=True)
    date = Column(String)
    oversize_dims = Column(String)  # free text, e.g. "27x20x6"
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    qty_of_oversize_items = Column(Integer)
    component_box_id = Column(Integer, ForeignKey("box_types.id"), nullable=False)
    component_qty_used = Column(Integer)
    reference_invoice_no = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    component_box = relationship("BoxType")


class BoxLedger(Base):
    """Append-only stock movement log — the real source of truth for stock."""
    __tablename__ = "box_ledger"

    id = Column(Integer, primary_key=True)
    box_id = Column(Integer, ForeignKey("box_types.id"), nullable=False)
    qty_change = Column(Integer, nullable=False)  # negative = deduction, positive = addition
    reference_type = Column(String, nullable=False)  # invoice | po | combination | correction
    reference_id = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    box = relationship("BoxType")
