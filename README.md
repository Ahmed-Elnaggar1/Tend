---
title: Tend
emoji: ⚡
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ⚡ Tend — Autonomous Open-Source Maintainer Triage Platform

An event-driven, production-grade AI maintainer assistant for GitHub repositories. Tend automatically ingests GitHub webhook events, performs semantic duplicate detection using vector embeddings (`pgvector`), triages issues using Google Gemini structured outputs, autonomous labeling, and posts intelligent responses directly to GitHub via an authentic GitHub App bot.

---

## 🌟 Architecture & Event-Driven Pipeline

```mermaid
flowchart TD
    A["GitHub Event: Issue Opened"] -->|HMAC-SHA256 Signed| B["FastAPI Webhook Receiver"]
    B -->|Verify Signature & Idempotency| C[("PostgreSQL Raw Events")]
    B -->|Fast 202 Accepted| G["Enqueued Job"]
    G --> D[("Redis Job Queue")]
    
    subgraph Worker ["Background Worker (ARQ)"]
        D --> E["Worker: triage_issue_task"]
        E -->|Generate 768-d Vector| F["Google Gemini Embedding"]
        F -->|Cosine Distance <= 0.2| H[("pgvector Table")]
        
        H -->|Duplicate Found?| I{"Match Found?"}
        I -->|YES| J["Mark Duplicate of #X & Generate Friendly Link"]
        I -->|NO| K["Run Structured Gemini AI Triage"]
        
        J --> L["GitHub App Bot Action"]
        K --> L
    end
    
    L -->|Post Comment + Apply Labels| M["GitHub Issue API"]
    
    subgraph Dashboard ["Maintainer Web Dashboard"]
        N["Browser / Client"] -->|GET /dashboard| O["FastAPI Static Server"]
        N -->|GET /api/stats & /api/issues| B
    end
```

---

## 🎯 Key Capabilities & Engineering Highlights

* **🔒 Cryptographic HMAC-SHA256 Verification**: Every incoming webhook payload is verified against the secret signature header before processing.
* **🛡️ Idempotent Event Ingestion**: Double deliveries and concurrent webhook race conditions are deduplicated at both the application layer and PostgreSQL unique constraints.
* **⚡ Zero-Blocking Webhook Processing**: Returns `202 Accepted` to GitHub in milliseconds, offloading AI inference and vector searches to a background queue via **Redis & ARQ**.
* **🧠 Vector Semantic Search with `pgvector`**: Converts issue titles and bodies into 768-dimensional vector embeddings using Google Gemini. Detects duplicates based on semantic meaning even if the user phrased the bug in completely different words!
* **🤖 Autonomous GitHub App Bot (Enterprise Auth)**: Authenticates dynamically using RSA private keys (`.pem`) and RS256 JWT signing to obtain short-lived installation access tokens. Comments and labels issues with an official `[bot]` badge.
* **📊 Maintainer Web Dashboard**: High-aesthetic dark-mode interface with glassmorphism, real-time counters, interactive priority filter pills, and live search.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | FastAPI (Python 3.12) | High-performance asynchronous REST API & Webhook receiver |
| **Database** | PostgreSQL 16 + `pgvector` | Relational storage + 768-dimension cosine distance similarity search |
| **ORM** | SQLAlchemy 2.0 (Async) + `asyncpg` | Non-blocking async database access |
| **Job Queue** | Redis 7 + `ARQ` | Distributed asynchronous task queue for AI workloads |
| **LLM Engine** | Google Gemini (`gemini-flash-lite-latest`) | Structured outputs (Pydantic schema validation) |
| **Embeddings** | Gemini (`gemini-embedding-001`) | 768-dimensional semantic text vectors |
| **Bot Auth** | PyJWT + `cryptography` | RS256 JWT generation for GitHub App installation tokens |
| **Testing** | `pytest` + `pytest-asyncio` + `httpx` | Automated async test suite |
| **Containerization**| Docker & Docker Compose | Multi-container production deployment |

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.12+
- Docker Desktop
- A Google Gemini API Key

### 2. Clone and Configure Environment
```bash
git clone https://github.com/Ahmed-Elnaggar1/Tend.git
cd Tend
```

Create a `.env` file in the root folder:
```env
GITHUB_WEBHOOK_SECRET=your_webhook_secret
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5433/triage_db
GEMINI_API_KEY=your_gemini_api_key
REDIS_URL=redis://localhost:6379

# GitHub App Bot Credentials (Optional for local testing, required for bot actions)
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY_PATH=your_private_key.pem
```

---

### 3. Running with Docker Compose (Recommended)

Start the entire platform (PostgreSQL + pgvector, Redis, FastAPI Web, and ARQ Worker) with a single command:

```bash
docker compose up --build -d
```

Initialize the database tables and pgvector extension:
```bash
docker compose exec web python -m app.create_tables
```

Now open your browser:
* 📊 **Maintainer Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
* 📋 **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 4. Running in Local Development Mode

#### Start Postgres and Redis:
```bash
docker compose up -d db redis
```

#### Install dependencies:
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python -m app.create_tables
```

#### Run the 3 development processes:
1. **Web Server**:
   ```bash
   uvicorn app.main:app --reload
   ```
2. **Webhook Forwarder (Smee)**:
   ```bash
   npx smee-client -u <YOUR_SMEE_URL> -t http://127.0.0.1:8000/webhooks/github
   ```
3. **Background Worker**:
   ```bash
   python -m arq app.worker.WorkerSettings
   ```

---

## 🧪 Running the Test Suite

Run the automated async test suite with `pytest`:

```bash
pytest -v
```

Expected output:
```text
tests/test_api.py::test_get_stats_endpoint PASSED                        [ 14%]
tests/test_api.py::test_get_issues_endpoint PASSED                       [ 28%]
tests/test_api.py::test_dashboard_serves_html PASSED                     [ 42%]
tests/test_api.py::test_triage_result_schema_validation PASSED           [ 57%]
tests/test_webhook_auth.py::test_webhook_rejects_missing_signature PASSED [ 71%]
tests/test_webhook_auth.py::test_webhook_rejects_invalid_signature PASSED [ 85%]
tests/test_webhook_auth.py::test_webhook_accepts_valid_signature PASSED  [100%]

============================== 7 passed in 0.39s ==============================
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/webhooks/github` | Ingests and verifies GitHub webhook events (`202 Accepted`) |
| `GET` | `/api/stats` | Real-time counts (total, open, high priority, duplicates) |
| `GET` | `/api/issues` | Query issues with filters (`?priority=high`, `?is_duplicate=true`, `?search=safari`) |
| `GET` | `/dashboard` | Interactive Maintainer Triage Dashboard UI |

---

## 📄 License
MIT License. Built for the open-source developer ecosystem.
