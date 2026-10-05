import pytest
import httpx
from httpx import ASGITransport
from app.main import app
from app.ai.schemas import TriageResult, IssueCategory, IssuePriority


@pytest.mark.asyncio
async def test_get_stats_endpoint():
    """Verify /api/stats returns status 200 and valid metric structure."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "open_count" in data
        assert "high_priority" in data
        assert "duplicates" in data
        assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_get_issues_endpoint():
    """Verify /api/issues returns status 200 and a list of serialized issues."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/issues")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_dashboard_serves_html():
    """Verify /dashboard returns HTTP 200 with HTML content."""
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        assert "Tend AI" in resp.text


def test_triage_result_schema_validation():
    """Verify Pydantic model validates structured AI responses properly."""
    result = TriageResult(
        summary="Safari checkout button hangs on mobile",
        priority=IssuePriority.HIGH,
        category=IssueCategory.BUG,
        draft_reply="Thank you for reporting this issue. We are investigating.",
    )
    assert result.priority == IssuePriority.HIGH
    assert result.category == IssueCategory.BUG
    assert "Safari checkout" in result.summary
