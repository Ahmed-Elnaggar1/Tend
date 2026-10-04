import os
from uuid import UUID
from arq.connections import RedisSettings
from dotenv import load_dotenv
from sqlalchemy import select

from app.ai.service import triage_issue_with_ai
from app.db import sessionmaker
from app.models import EventStatus, Issue, Priority, WebhookEvent

load_dotenv()


async def triage_issue_task(
    ctx,
    issue_id: str,
    delivery_id: str,
    title: str,
    body: str | None,
) -> None:
    print(f"🤖 [ARQ Worker] Starting AI triage for: {title}...")

    # 1. Ask Gemini to analyze the issue
    ai_result = await triage_issue_with_ai(title, body)

    # 2. Persist the results to PostgreSQL
    async with sessionmaker() as db:
        issue = await db.get(Issue, UUID(issue_id))
        if not issue:
            print(f"❌ [ARQ Worker] Issue {issue_id} not found in DB!")
            return

        issue.priority = Priority(ai_result.priority.value)
        issue.ai_summary = ai_result.summary
        issue.draft_reply = ai_result.draft_reply

        event = await db.scalar(
            select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
        )
        if event:
            event.status = EventStatus.COMPLETED

        await db.commit()
        print(f"✅ [ARQ Worker] Triage completed for issue #{issue.issue_number}")
        print(f"   Priority: {issue.priority}")
        print(f"   Summary:  {issue.ai_summary}")


class WorkerSettings:
    functions = [triage_issue_task]
    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379")
    )
