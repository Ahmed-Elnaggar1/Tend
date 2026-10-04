from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EventStatus,
    WebhookEvent,
    Issue,
    Priority,
    State
    )
from app.ai.service import triage_issue_with_ai
from app.db import sessionmaker

# 1. Read: Check if this delivery was already recorded
async def get_webhook_event_by_delivery_id(
    db: AsyncSession, delivery_id: str
) -> WebhookEvent | None:
  result = await db.scalar(
      select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
  )
  return result


# 2. Create: Save a new incoming webhook event
async def create_webhook_event(
    db: AsyncSession,
    delivery_id: str,
    event_type: str,
    payload: dict,
) -> WebhookEvent:
  event = WebhookEvent(
      delivery_id=delivery_id,
      event_type=event_type,
      payload=payload,
      status=EventStatus.PENDING,
  )
  db.add(event)
  await db.commit()
  await db.refresh(event)
  return event


async def upsert_issue_from_payload(
    db: AsyncSession, payload: dict, action: str
) -> Issue | None:
  issue_data = payload.get("issue")
  repo_data = payload.get("repository")

  # Ignore events that don't have issue data
  if not issue_data or not repo_data:
    return None

  github_id = str(issue_data["id"])

  # Check if issue already exists in our table
  issue = await db.scalar(select(Issue).where(Issue.github_id == github_id))

  # Determine state
  if action == "deleted":
    current_state = State.DELETED
  elif issue_data.get("state") == "closed":
    current_state = State.CLOSED
  else:
    current_state = State.OPEN

  if not issue:
    # 🆕 Create new issue
    issue = Issue(
        github_id=github_id,
        issue_number=issue_data["number"],
        repo_name=repo_data["full_name"],
        title=issue_data["title"],
        body=issue_data.get("body"),
        author=issue_data["user"]["login"],
        state=current_state,
    )
    db.add(issue)
  else:
    # 🔄 Update existing issue
    issue.title = issue_data["title"]
    issue.body = issue_data.get("body")
    issue.state = current_state

  await db.commit()
  await db.refresh(issue)
  return issue

async def process_issue_triage(
    issue_id: UUID,
    delivery_id: str,
    title:str,
    body:str|None,
) -> None:
    print(f"🤖 Starting AI triage for issue {title}...")

    ai_result = await triage_issue_with_ai(title,body)
    async with sessionmaker() as db:
        issue = await db.get(Issue,issue_id)
        if not issue:
            print(f"❌ Issue {issue_id} not found in DB!")
            return
        
        issue.priority = ai_result.priority
        issue.ai_summary = ai_result.summary
        issue.draft_reply = ai_result.draft_reply
        event = await db.scalar(
            select(WebhookEvent).where(
                WebhookEvent.delivery_id == delivery_id
            )
        )
        if event:
            event.status = EventStatus.COMPLETED
        await db.commit()
        print(f"✅ AI Triage completed for issue #{issue.issue_number}")
        print(f"   Priority: {issue.priority}")
        print(f"   Summary: {issue.ai_summary}")
    
    