"""TradingView Webhook: eingehende Signale empfangen und optional zu Aktionen mappen."""

from __future__ import annotations

import json
import logging
import os
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# --- Signale (optional; nur wenn der Alert-Text exakt passt) ---


class TradeAction(str, Enum):
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


SIGNAL_MAP: dict[str, TradeAction] = {
    "AI BULLISH REVERSAL": TradeAction.ENTRY_LONG,
    "AI BEARISH REVERSAL": TradeAction.ENTRY_SHORT,
    "RES Test": TradeAction.EXIT_LONG,
    "SUP Test": TradeAction.EXIT_SHORT,
}


def parse_alert_text(raw: str) -> TradeAction | None:
    text = (raw or "").strip()
    if not text:
        return None
    return SIGNAL_MAP.get(text)


def _extract_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("message", "text", "alert", "content"):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _verify_secret(x_webhook_secret: str | None, authorization: str | None) -> None:
    if not WEBHOOK_SECRET:
        return
    if x_webhook_secret == WEBHOOK_SECRET:
        return
    if authorization and authorization.startswith("Bearer "):
        if authorization.removeprefix("Bearer ").strip() == WEBHOOK_SECRET:
            return
    raise HTTPException(status_code=401, detail="invalid webhook secret")


app = FastAPI(title="TradingView Webhook", version="0.2.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _verify_secret(x_webhook_secret, authorization)

    raw_body = await request.body()
    payload: Any = None
    text = ""

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        text = _extract_message(payload)
    except json.JSONDecodeError:
        text = raw_body.decode("utf-8", errors="replace").strip()

    action = parse_alert_text(text)
    out: dict[str, Any] = {
        "ok": True,
        "message": text,
        "action": action.value if action else None,
    }
    if isinstance(payload, dict):
        out["payload"] = payload

    logger.info("Webhook: %s", out)
    return out
