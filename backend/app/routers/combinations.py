from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.combinations import log_combinations_batch, check_recurring_oversize_patterns
from app.schemas import CombinationBatchIn

router = APIRouter(prefix="/combinations", tags=["combinations"])


@router.post("/log-batch")
def log_batch(payload: CombinationBatchIn, db: Session = Depends(get_db)):
    entries = [e.model_dump() for e in payload.entries]
    results = log_combinations_batch(db, entries)
    return {"results": results}


@router.get("/recurring-patterns")
def recurring_patterns(db: Session = Depends(get_db)):
    return {"patterns": check_recurring_oversize_patterns(db)}
