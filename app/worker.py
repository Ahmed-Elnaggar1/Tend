from app import crud
import os
from uuid import UUID
from arq.connections import RedisSettings
from dotenv import load_dotenv
from sqlalchemy import select

from app.ai.service import triage_issue_with_ai, generate_embedding
from app.db import sessionmaker
from app.models import EventStatus, Issue, Priority, WebhookEvent

load_dotenv()


async def triage_issue_task(
    ctx, issue_id: str, delivery_id: str, title: str, body: str | None
) -> None:
  print(f"🤖 [ARQ Worker] Processing issue: {title}...")
  # 1. Generate 768-d vector embedding for this issue
  text_to_embed = f"{title}\n{body or ''}"
  embedding = await generate_embedding(text_to_embed)
  async with sessionmaker() as db:
    issue = await db.get(Issue, UUID(issue_id))
    if not issue:
      return
    # Store the embedding on the issue row
    issue.embedding = embedding
    # 2. Check for semantic duplicates in PostgreSQL using pgvector!
    duplicate = await crud.find_most_similar_issue(
        db=db,
        repo_name=issue.repo_name,
        embedding=embedding,
        exclude_issue_id=issue.id,
    )
    if duplicate:
      print(f"🎯 DUPLICATE DETECTED! Matches issue #{duplicate.issue_number}")
      issue.duplicate_of_id = duplicate.id
      issue.priority = Priority.LOW
      issue.ai_summary = (
          f"Duplicate of #{duplicate.issue_number}: {duplicate.title}"
      )
      issue.draft_reply = (
          f"Hello! Thank you for opening this issue. This appears to be a"
          f" duplicate of #{duplicate.issue_number} ('{duplicate.title}')."
          " Please check the ongoing discussion and solution there!"
      )
    else:
      # 3. Not a duplicate? Run full AI triage!
      ai_result = await triage_issue_with_ai(title, body)
      issue.priority = Priority(ai_result.priority.value)
      issue.ai_summary = ai_result.summary
      issue.draft_reply = ai_result.draft_reply
    # Mark the event completed
    event = await db.scalar(
        select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
    )
    if event:
      event.status = EventStatus.COMPLETED
    await db.commit()
    print(f"✅ [ARQ Worker] Completed processing for #{issue.issue_number}")


class WorkerSettings:
    functions = [triage_issue_task]
    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379")
    )
