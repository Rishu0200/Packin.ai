"""Sends low-stock/review alerts to Telegram, optionally with the
generated Excel/PDF report attached."""
import requests
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

API_BASE = "https://api.telegram.org/bot{token}"


def send_message(text: str) -> dict:
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN not configured"}
    url = f"{API_BASE.format(token=TELEGRAM_BOT_TOKEN)}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    return resp.json()


def send_document(file_buffer, filename: str, caption: str = "") -> dict:
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN not configured"}
    url = f"{API_BASE.format(token=TELEGRAM_BOT_TOKEN)}/sendDocument"
    files = {"document": (filename, file_buffer)}
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
    resp = requests.post(url, data=data, files=files)
    return resp.json()
