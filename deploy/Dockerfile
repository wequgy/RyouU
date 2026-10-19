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
COPY services/api/ services/api/
COPY sdks/ sdks/
COPY scripts/ scripts/

RUN pip install --no-cache-dir -e "services/api[all]"

COPY . .

# Download and verify models with pinned checksums
RUN python -m scripts.download_models

# Run undeclared import scanner during container build
RUN python scripts/check_undeclared_imports.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
