"""
Connects the reorder agent's low-stock check to actual Telegram delivery.
This was the missing piece — send_message()/send_document() existed but
nothing was calling them after a real stock change."""
from sqlalchemy.orm import Session
from app.agents.reorder_agent import check_low_stock
from app.agents import telegram_bot
from app.core.exports import build_excel_report


def notify_low_stock_if_any(db: Session, trigger: str = "") -> dict:
    """Call this after any invoice/PO processing that could have changed
    stock levels. Sends one consolidated message (not one per box) so a
    single upload with several affected sizes doesn't spam the group."""
    low = check_low_stock(db)
    if not low:
        return {"status": "no_low_stock"}

    lines = [f"⚠️ PackIn.ai — {len(low)} box size(s) low on stock"
              + (f" (after {trigger})" if trigger else "") + ":"]
    for item in low:
        lines.append(f"• {item['size']} — {item['brand']}: {item['current_stock']} left "
                      f"(suggest reordering {item['suggested_reorder_qty']})")
    message = "\n".join(lines)

    result = telegram_bot.send_message(message)

    # Attach the current inventory report so the group has the full picture,
    # not just the flagged rows.
    try:
        report = build_excel_report(db)
        telegram_bot.send_document(report, "packin_inventory_report.xlsx",
                                    caption="Current full inventory")
    except Exception:
        pass  # report attachment is a nice-to-have; don't fail the alert over it

    return {"status": "sent", "low_stock_count": len(low), "telegram_response": result}