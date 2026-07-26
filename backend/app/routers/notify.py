from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.agents import telegram_bot
from app.core.notifications import notify_low_stock_if_any
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

router = APIRouter(prefix="/notify", tags=["notifications"])


@router.get("/test-telegram")
def test_telegram():
    """Call this on its own first, before debugging the full pipeline —
    isolates whether TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID are configured
    correctly, independent of any stock logic."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {
            "status": "not_configured",
            "reason": "TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID missing from .env",
        }
    result = telegram_bot.send_message("✅ PackIn.ai test message — Telegram is wired up correctly.")
    return {"status": "attempted", "telegram_response": result}


@router.post("/check-low-stock")
def manually_trigger_low_stock_check(db: Session = Depends(get_db)):
    """Manual trigger — useful for testing, or as a cron-job endpoint if you
    want a periodic check independent of invoice/PO uploads."""
    return notify_low_stock_if_any(db, trigger="manual check")