import os
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx
import jwt

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")

def get_app_jwt() -> str:
    """Generate a signed JWT asserting our GitHub App identity (valid 10 mins)."""
    # 1. Read the RSA private key file
    pem_path = Path(PRIVATE_KEY_PATH)
    if not pem_path.exists():
        raise FileNotFoundError(f"GitHub private key not found at {pem_path}")
    
    private_key = pem_path.read_text()

    # 2. Prepare JWT claims required by GitHub
    now = int(time.time())
    payload = {
        # Issued at time (subtract 60 seconds to tolerate server clock drift)
        "iat": now - 60,
        # Expiration time (GitHub allows max 10 mins; use 8 mins to tolerate local clock drift)
        "exp": now + (8 * 60),
        # Issuer: our GitHub App ID
        "iss": APP_ID,
    }
    # 3. Sign using RSA algorithm SHA-256
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
    return encoded_jwt

async def get_installation_token(repo_name: str) -> str:
    """Exchange our App JWT for a temporary installation token for a specific repository."""
    app_jwt = get_app_jwt()
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        # Step A: Find the installation ID for this repository
        install_url = f"https://api.github.com/repos/{repo_name}/installation"
        resp = await client.get(install_url, headers=headers)
        resp.raise_for_status()
        installation_id = resp.json()["id"]
        # Step B: Request an installation access token
        token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        token_resp = await client.post(token_url, headers=headers)
        token_resp.raise_for_status()
        # Returns a token like 'ghs_...' valid for 1 hour
        return token_resp.json()["token"]
async def post_issue_comment(repo_name: str, issue_number: int, comment: str) -> dict:
    """Post a comment on a GitHub issue as the GitHub App Bot."""
    token = await get_installation_token(repo_name)
    url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"body": comment}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
async def add_issue_labels(repo_name: str, issue_number: int, labels: list[str]) -> list[dict]:
    """Add labels (e.g. ['duplicate', 'priority: high']) to a GitHub issue."""
    token = await get_installation_token(repo_name)
    url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"labels": labels}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
