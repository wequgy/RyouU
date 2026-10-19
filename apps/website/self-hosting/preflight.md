---
title: Preflight Checks & Readiness Probes
description: Kubernetes readiness (/readyz) and liveness (/healthz) endpoints and preflight model warmups.
---

RyouU exposes enterprise health check probes and a dedicated preflight script to ensure neural models are warm before routing live production traffic.

---

## 1. Health and Readiness Endpoints

### `/healthz` (Liveness Probe)
Returns HTTP 200 as long as the Uvicorn web process is accepting HTTP connections:

```bash
curl http://localhost:8000/healthz
```
Response:
```json
{"status": "ok"}
```

### `/readyz` (Readiness Probe)
Returns HTTP 200 only when:
1. PostgreSQL database connection is alive and migrations are current.
2. All required local ONNX models (`face_landmarker.task`, `minifasnet_v2.onnx`, `rapidocr`) are downloaded and mapped into memory.
3. Media directories are writable.

```bash
curl http://localhost:8000/readyz
```
Response:
```json
{
  "status": "ready",
  "database": "connected",
  "models": {
    "insightface": "ready",
    "mediapipe": "ready",
    "minifasnet": "ready",
    "rapidocr": "ready"
  }
}
```

If models are still downloading or initializing, `/readyz` returns HTTP 503.

---

## 2. Running Warmup Scripts

Execute the warm-up script during container image builds or Kubernetes init-containers:

```bash
python scripts/warmup.py
```

This runs synthetic forward passes through InsightFace, MediaPipe, and MiniFASNet to compile JIT graph optimizations and ensure sub-second response times on the very first live verification request.
