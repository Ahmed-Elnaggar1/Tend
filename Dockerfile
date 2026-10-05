FROM python:3.12-slim

WORKDIR /app

# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install basic networking/curl tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 8000

# Default command runs the web server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
