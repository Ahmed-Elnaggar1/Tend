from app.ai.service import triage_issue_with_ai

if __name__ == "__main__":
  import asyncio

  async def test():
    result = await triage_issue_with_ai(
        title="App crashes immediately on login",
        body="When I click the login button with valid credentials, the entire window closes without error.",
    )
    print("\n--- AI TRIAGE RESULT ---")
    print(f"Category: {result.category}")
    print(f"Priority: {result.priority}")
    print(f"Summary:  {result.summary}")
    print(f"Reply:    {result.draft_reply}")

  asyncio.run(test())
