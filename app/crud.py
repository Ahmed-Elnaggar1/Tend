from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import (
  select,
  func,
)
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

async def find_most_similar_issue(
    db: AsyncSession,
    repo_name: str,
    embedding: list[float],
    exclude_issue_id: UUID,
    max_distance: float = 0.2,
) -> Issue | None:
  query = (
      select(Issue)
      .where(
          Issue.repo_name == repo_name,
          Issue.id != exclude_issue_id,
          Issue.embedding.is_not(None),
          Issue.embedding.cosine_distance(embedding) <= max_distance,

      )
      .order_by(Issue.embedding.cosine_distance(embedding))
      .limit(1)
  )

  result = await db.scalar(query)
  if result:
    # Check if the closest match is within our duplicate threshold (distance < 0.2)
    # If the distance is small enough, it's a duplicate!
    return result

  return None


async def count_issues(
  db:AsyncSession,
  state: State|None=None,
  priority: Priority|None=None,
  is_duplicate: bool|None=None,
) ->int:
  """Count issues matching optional filters."""
  query=select(func.count(Issue.id))
    
  if state is not None:
    query = query.where(Issue.state == state)
  if priority is not None:
    query = query.where(Issue.priority == priority)
  if is_duplicate is True:
    query = query.where(Issue.duplicate_of_id.is_not(None))
  elif is_duplicate is False:
    query = query.where(Issue.duplicate_of_id.is_(None))
    
  result = await db.scalar(query)
  return result or 0
    

async def get_issues(
  db:AsyncSession,
  priority: Priority | None = None,
  search: str | None = None,
  is_duplicate: bool|None=None,
) -> Sequence[Issue]:
  """Retrieve a list of issues with optional filtering."""
  query = select(Issue).order_by(Issue.created_at.desc())

  if priority is not None:
    query = query.where(Issue.priority == priority)
  if is_duplicate is True:
    query = query.where(Issue.duplicate_of_id.is_not(None))
  elif is_duplicate is False:
    query = query.where(Issue.duplicate_of_id.is_(None))
  if search:
    query = query.where(Issue.title.ilike(f"%{search}%"))
  result = await db.scalars(query)
  return result.all()
    