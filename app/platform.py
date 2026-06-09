"""Outbound client for the WhatsApp platform /api/send-message endpoint."""
from typing import Optional

import httpx

from .config import settings


async def send_message(phone_number: str, content: str, media: Optional[dict] = None) -> dict:
    """POST to the platform. `media` = {"type": "image|document|audio|video", "data": <base64>, "filename": ...}."""
    if not settings.platform_send_url or not settings.platform_api_key:
        return {"skipped": True, "reason": "PLATFORM_SEND_URL / PLATFORM_API_KEY not configured"}

    body: dict = {"phoneNumber": phone_number, "content": content}
    if media:
        body["media"] = media

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            settings.platform_send_url,
            headers={"X-API-Key": settings.platform_api_key, "Content-Type": "application/json"},
            json=body,
        )
        try:
            return {"status": r.status_code, "data": r.json()}
        except Exception:
            return {"status": r.status_code, "text": r.text[:300]}
