#!/bin/bash
set -e

# Start the ARQ background worker in the background
echo "Starting ARQ background triage worker..."
python -m arq app.worker.WorkerSettings &

# Start the FastAPI web server on the port assigned by cloud host ($PORT or 8000)
PORT="${PORT:-8000}"
echo "Starting FastAPI web server on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
