import os, hmac, hashlib, json, time
from typing import Dict, Any, Optional
import requests
from flask import current_app

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # optional

def _sign(body: bytes) -> str:
    if not WEBHOOK_SECRET:
        return ""
    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"

def deliver_webhook(url: str, event: str, data: Dict[str, Any], timeout: float = 10.0) -> tuple[int, str]:
    """
    Best-effort delivery with exponential backoff. Treats 2xx/4xx as terminal,
    retries on network errors and 5xx (up to ~5 attempts).
    """
    body = json.dumps({"event": event, "data": data}, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "mdraft-webhook/1.0",
    }
    sig = _sign(body)
    if sig:
        headers["X-MDraft-Signature"] = sig

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.post(url, data=body, headers=headers, timeout=timeout)
            code = resp.status_code
            # 2xx or 4xx => don't retry
            if 200 <= code < 300 or 400 <= code < 500:
                return code, resp.text
        except Exception as e:
            code, resp_text = 0, str(e)

        if attempt >= 5:
            if current_app:
                current_app.logger.error("webhook_failed", extra={"url": url, "event": event, "attempts": attempt, "last_code": code})
            return code, resp_text

        # backoff 1,2,4,8 seconds (cap at 10)
        time.sleep(min(2 ** (attempt - 1), 10))
