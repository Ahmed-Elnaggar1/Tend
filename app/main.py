from contextlib import asynccontextmanager
import hashlib
import hmac
import json
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app import crud
from app.config import settings
from app.db import get_db_session
from app.models import State, Priority
from app.worker import triage_issue_task


def verify_github_signature(body_bytes: bytes, signature_header: str | None):
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header",
        )

    if not settings.GITHUB_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )

    hash_object = hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
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
    # Connect to Redis for the ARQ job queue on startup (graceful fallback if serverless)
    try:
        app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        print("🔌 Connected to Redis job queue (ARQ)!")
    except Exception as e:
        print(f"⚠️ Redis connection optional/deferred: {e}")
        app.state.arq_pool = None
    yield
    # Clean up connection pool on shutdown if initialized
    if getattr(app.state, "arq_pool", None):
        await app.state.arq_pool.close()
        print(" Disconnected from Redis job queue.")


app = FastAPI(lifespan=lifespan)


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
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

        try:
            # 5. Persist raw event to Postgres
            await crud.create_webhook_event(
                db=db,
                delivery_id=delivery_id,
                event_type=event_type,
                payload=payload,
            )
        except IntegrityError:
            await db.rollback()
            print(f"⚠️ Concurrent duplicate delivery caught: {delivery_id}")
            return {"status": "already_received", "delivery_id": delivery_id}

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
                pool = getattr(request.app.state, "arq_pool", None)
                if pool:
                    try:
                        # 🚀 Enqueue background task in Redis via ARQ!
                        await pool.enqueue_job(
                            "triage_issue_task",
                            issue_id=str(saved_issue.id),
                            delivery_id=delivery_id,
                            title=saved_issue.title,
                            body=saved_issue.body,
                        )
                        print(f" Enqueued AI triage job in Redis for #{saved_issue.issue_number}")
                    except Exception as e:
                        print(f"⚠️ Redis enqueue failed ({e}), executing via background task fallback")
                        background_tasks.add_task(
                            triage_issue_task,
                            None,
                            str(saved_issue.id),
                            delivery_id,
                            saved_issue.title,
                            saved_issue.body,
                        )
                else:
                    # Serverless direct background execution!
                    background_tasks.add_task(
                        triage_issue_task,
                        None,
                        str(saved_issue.id),
                        delivery_id,
                        saved_issue.title,
                        saved_issue.body,
                    )
                    print(f" Scheduled background AI triage task for #{saved_issue.issue_number}")

        print(f" Saved webhook event to DB: {event_type} (Delivery ID: {delivery_id})")

    return {"status": "accepted", "delivery_id": delivery_id}

@app.get("/api/stats")
async def get_summary(db: AsyncSession = Depends(get_db_session)):
    total = await crud.count_issues(db)
    open_count = await crud.count_issues(db, state=State.OPEN)
    high_priority = await crud.count_issues(db, priority=Priority.HIGH)
    duplicates = await crud.count_issues(db, is_duplicate=True)

    return {
        "total": total or 0,
        "open_count": open_count or 0,
        "high_priority": high_priority or 0,
        "duplicates": duplicates or 0,
    }

@app.get("/api/issues")
async def get_issues(
    priority: str | None = None,
    is_duplicate: bool | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    priority_enum = None
    if priority:
        try:
            priority_enum = Priority(priority.lower())
        except ValueError:
            pass

    issues = await crud.get_issues(
        db=db,
        priority=priority_enum,
        is_duplicate=is_duplicate,
        search=search,
    )
    return [
        {
            "id": str(i.id),
            "issue_number": i.issue_number,
            "repo_name": i.repo_name,
            "title": i.title,
            "body": i.body,
            "author": i.author,
            "state": i.state.value if i.state else None,
            "priority": i.priority.value if i.priority else None,
            "ai_summary": i.ai_summary,
            "draft_reply": i.draft_reply,
            "duplicate_of_id": str(i.duplicate_of_id) if i.duplicate_of_id else None,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in issues
    ]
# Mount static folder
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/dashboard")
async def serve_dashboard():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Dashboard index.html not found"}

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
