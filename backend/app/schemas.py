from pydantic import BaseModel
from typing import Optional


class BrandCreate(BaseModel):
    name: str


class CustomerMapRequest(BaseModel):
    customer_name: str
    brand_id: int


class SubstitutionConfirm(BaseModel):
    line_item_id: int
    chosen_box_id: int


class BrandCorrection(BaseModel):
    original_box_id: int
    corrected_box_id: int
    qty: float
    reference_id: str
    notes: Optional[str] = None


class CombinationEntryIn(BaseModel):
    date: str
    oversize_dims: str
    brand_id: Optional[int] = None
    qty_of_oversize_items: int
    component_box_id: int
    component_qty_used: int
    reference_invoice_no: Optional[str] = None
    notes: Optional[str] = None


class CombinationBatchIn(BaseModel):
    entries: list[CombinationEntryIn]
