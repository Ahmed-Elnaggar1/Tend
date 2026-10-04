from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from arq import create_pool
from arq.connections import RedisSettings
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db import get_db_session

load_dotenv()
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def verify_github_signature(body_bytes: bytes, signature_header: str | None):
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header",
        )

    if not WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )

    hash_object = hmac.new(
        key=WEBHOOK_SECRET.encode("utf-8"),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Redis for the ARQ job queue on startup
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    print("🔌 Connected to Redis job queue (ARQ)!")
    yield
    # Clean up connection pool on shutdown
    await app.state.arq_pool.close()
    print(" Disconnected from Redis job queue.")


app = FastAPI(lifespan=lifespan)


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    # 1. Read raw body & headers
    body_bytes = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    delivery_id = request.headers.get("x-github-delivery")
    event_type = request.headers.get("x-github-event", "unknown")

    # 2. Cryptographic signature check
    verify_github_signature(body_bytes, signature)

    # 3. Parse JSON payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        payload = {}

    # 4. Idempotency check: has this delivery already been received?
    if delivery_id:
        existing_event = await crud.get_webhook_event_by_delivery_id(db, delivery_id)
        if existing_event:
            print(f" Duplicate delivery ignored: {delivery_id}")
            return {"status": "already_received", "delivery_id": delivery_id}

        # 5. Persist raw event to Postgres
        await crud.create_webhook_event(
            db=db,
            delivery_id=delivery_id,
            event_type=event_type,
            payload=payload,
        )

        # 6. If it's an issue event, create/update the Issue row!
        if event_type == "issues":
            action = payload.get("action", "")
            saved_issue = await crud.upsert_issue_from_payload(
                db=db, payload=payload, action=action
            )
            if saved_issue and action in ["opened", "edited"]:
                print(
                    f" Upserted issue #{saved_issue.issue_number} ({saved_issue.state}) into issues table!"
                )
                # 🚀 Enqueue background task in Redis via ARQ!
                await request.app.state.arq_pool.enqueue_job(
                    "triage_issue_task",
                    issue_id=str(saved_issue.id),
                    delivery_id=delivery_id,
                    title=saved_issue.title,
                    body=saved_issue.body,
                )
                print(f" Enqueued AI triage job in Redis for #{saved_issue.issue_number}")

        print(f" Saved webhook event to DB: {event_type} (Delivery ID: {delivery_id})")

    return {"status": "accepted", "delivery_id": delivery_id}