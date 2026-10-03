import hashlib
import hmac
import os
from dotenv import load_dotenv

import json
from fastapi import FastAPI, Request, status , HTTPException

load_dotenv()
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


def verify_github_signature(body_bytes:bytes, signature_header:str|None):
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED , detail="Missing signature header")

    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail="Webhook secret not configured")

    hash_object = hmac.new(key=WEBHOOK_SECRET.encode('utf-8'), msg=body_bytes, digestmod=hashlib.sha256)

    expected_signature = 'sha256=' + hash_object.hexdigest()

    if not hmac.compare_digest(signature_header , expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED , detail="Invalid signature")


app = FastAPI()


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(request:Request):
    body_bytes = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    verify_github_signature(body_bytes, signature)

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