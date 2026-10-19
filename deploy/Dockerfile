FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system libraries needed by OpenCV, MediaPipe, Faster-Whisper, and SyncNet
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY requirements.txt .
COPY requirements-all.lock .

RUN pip install --no-cache-dir -r requirements-all.lock || pip install --no-cache-dir ".[kyc,interview,postgres,dev]"

COPY . .

# Run preflight and validation during container verification if desired
RUN python scripts/check_undeclared_imports.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
