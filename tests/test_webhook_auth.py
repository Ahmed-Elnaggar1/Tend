import hashlib
import hmac
import json
import os
import pytest
import httpx
from httpx import ASGITransport
from app.main import app


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature():
    """Ensure requests without an x-hub-signature-256 header are rejected."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/webhooks/github", json={"action": "test"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing signature header"


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature():
    """Ensure requests with tampered or incorrect HMAC signatures are blocked."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {
            "x-hub-signature-256": "sha256=badsignature0000000000000000000000000000000000000000000000000000",
            "x-github-delivery": "test-delivery-tampered",
            "x-github-event": "ping",
        }
        resp = await client.post("/webhooks/github", json={"zen": "test"}, headers=headers)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid signature"


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature():
    """Ensure authentic payloads with valid cryptographic HMAC signatures are accepted."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "my_test_secret").strip()
    payload = {"zen": "Keep it logically awesome."}
    payload_bytes = json.dumps(payload).encode("utf-8")
    valid_sig = compute_signature(payload_bytes, secret)

    import uuid
    headers = {
        "x-hub-signature-256": valid_sig,
        "x-github-delivery": f"test-delivery-{uuid.uuid4()}",
        "x-github-event": "ping",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/webhooks/github", content=payload_bytes, headers=headers)
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"
