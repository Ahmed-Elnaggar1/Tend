import json
from fastapi import FastAPI, Request, status

app = FastAPI()


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(request:Request):
    body_bytes = await request.body()


    event_type = request.headers.get("x-github-event", "unknown")
    signature = request.headers.get("x-hub-signature-256")
    print(f" Received event: {event_type}")
    print(f" Signature header: {signature}")
    try:
       payload = json.loads(body_bytes)
       action = payload.get("action", "no action")
       print(f" Action: {action}")
    except json.JSONDecodeError:
       payload = {}
    # 4. Immediately reply to GitHub: 'Got it!'
    return {"status": "accepted"}