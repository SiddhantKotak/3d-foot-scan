"""KIRI webhook receiver.

Verifies the HMAC signature, maps the KIRI serialize back to its thread_id, and
resumes await_reconstruction with the model_url. Active only when PUBLIC_URL +
webhook secret are configured; otherwise the polling path in
await_reconstruction handles completion.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from ..adapters.kiri import KiriClient, STATUS_SUCCESS
from ..config import get_settings
from ..storage import thread_for_serialize

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/kiri")
async def kiri_webhook(
    request: Request,
    x_webhook_timestamp: str = Header(default=""),
    x_webhook_signature: str = Header(default=""),
) -> dict:
    settings = get_settings()
    secret = settings.kiri_webhook_secret
    if not secret:
        raise HTTPException(400, "webhook secret not configured")

    body = await request.json()
    serialize = str(body.get("serialize") or body.get("taskId") or "")
    if not KiriClient.verify_webhook(serialize, x_webhook_timestamp, x_webhook_signature, secret):
        raise HTTPException(401, "bad signature")

    status = int(body.get("status", STATUS_SUCCESS))
    thread_id = thread_for_serialize(serialize)
    if thread_id is None:
        raise HTTPException(404, f"unknown serialize {serialize}")
    if status != STATUS_SUCCESS:
        return {"ok": True, "ignored_status": status}

    kiri = KiriClient(settings)
    model_url = kiri.get_download_url(serialize)
    request.app.state.runs.resume_reconstruction(thread_id, model_url)
    return {"ok": True, "resumed": thread_id}
