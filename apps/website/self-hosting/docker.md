---
title: Docker Deployment
description: Running RyouU in production with Docker Compose, resource allocation, and container architecture.
---

RyouU ships with multi-stage Dockerfiles optimized for lightweight CPU-only inference using ONNX Runtime and CTranslate2.

---

## 1. Quick Launch with Docker Compose

```bash
# Clone the repository
git clone https://github.com/wequgy/RyouU.git
cd RyouU

# Configure your production environment
cp .env.example .env
nano .env

# Launch containers
docker compose up -d
```

Containers launched:
- **`kyc-api`**: FastAPI service running Uvicorn workers on port 8000.
- **`postgres`**: PostgreSQL 16 database storing verification states and audit logs.

---

## 2. Resource Recommendations

| Workload Volume | CPU Cores | RAM | Storage |
| :--- | :--- | :--- | :--- |
| **Development / Testing** | 2 cores | 4 GB | 10 GB SSD |
| **Production (100 verifications/hr)** | 4 cores | 8 GB | 50 GB SSD |
| **Enterprise (1,000+ verifications/hr)** | 8–16 cores | 16–32 GB | 200 GB SSD + S3 Object Storage |

---

## 3. Persistent Volumes

Ensure that the data volume persists across container upgrades:

```yaml
volumes:
  kyc_data:
    driver: local
  postgres_data:
    driver: local
```

The `kyc_data` volume retains downloaded neural models (`models/face_landmarker.task`, `models/minifasnet_v2.onnx`) so containers restart instantly without downloading weights repeatedly.
