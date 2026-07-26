from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.exports import get_stock_rows, build_excel_report, build_pdf_report
from app.agents.reorder_agent import check_low_stock

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("")
def list_inventory(db: Session = Depends(get_db)):
    return {"stock": get_stock_rows(db)}


@router.get("/low-stock")
def low_stock(db: Session = Depends(get_db)):
    return {"low_stock": check_low_stock(db)}


@router.get("/export")
def export_inventory(format: str = "xlsx", db: Session = Depends(get_db)):
    if format == "pdf":
        buffer = build_pdf_report(db)
        media_type = "application/pdf"
        filename = "packin_inventory_report.pdf"
    else:
        buffer = build_excel_report(db)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "packin_inventory_report.xlsx"

    return StreamingResponse(
        buffer, media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
