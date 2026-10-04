from enum import StrEnum
from pydantic import BaseModel, Field

class IssueCategory(StrEnum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    OTHER = "other"

class IssuePriority(StrEnum):
  HIGH = "high"
  MEDIUM = "medium"
  LOW = "low"
class TriageResult(BaseModel):
    category: IssueCategory = Field(
      description="The classification of this issue"
    )
    priority: IssuePriority = Field(
      description="Urgency: high for crashes/security, medium for normal bugs/features, low for minor questions"
    )
    summary: str = Field(
      description="A concise 1-sentence summary of what the author is reporting"
    )
    draft_reply: str = Field(
      description="A polite, empathetic, and professional draft response from the maintainer"
    )
  
