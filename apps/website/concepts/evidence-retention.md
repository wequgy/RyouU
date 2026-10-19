---
title: Evidence & Retention
description: Storage architecture for raw biometric media, encryption at rest, and automated data purging.
---

Identity verification inherently processes sensitive Personally Identifiable Information (PII) and biometric data. RyouU provides server-side controls to encrypt evidence at rest and purge raw assets according to your jurisdiction's data retention laws.

---

## 1. Biometric Evidence Artifacts

During a verification session, RyouU captures and processes several distinct artifacts:

| Artifact Kind | Format | Content | Sensitive Level |
| :--- | :--- | :--- | :--- |
| **`id_front`** | JPEG / WebP | Front scan of national ID card, driver's license, or passport. | High PII |
| **`id_back`** | JPEG / WebP | Reverse scan containing address, barcode, or metadata. | High PII |
| **`selfie`** | JPEG | High-resolution face crop taken during active liveness. | Biometric |
| **`video_liveness`** | WebM / MP4 | Video stream recording of voluntary head movements and blinks. | Biometric |
| **`audio_challenge`** | WAV / AAC | Spoken challenge audio recording used for voiceprint enrollment. | Biometric |

---

## 2. Evidence Retrieval API

Only authenticated tenant API keys with `kyc:read` scope can retrieve evidence media:

```bash
# Fetch the list of captured evidence items
curl http://localhost:8000/v1/verifications/ver_9a482b1c/evidence \
  -H "Authorization: Bearer kyc_live_..."

# Stream an individual encrypted artifact
curl http://localhost:8000/v1/verifications/ver_9a482b1c/evidence/id_front \
  -H "Authorization: Bearer kyc_live_..." \
  --output id_front.jpg
```

---

## 3. Automated Retention & Purging Policies

To comply with data minimization regulations (such as GDPR Article 5(1)(e) or India's DPDP Act), RyouU supports automated evidence lifecycle policies:

```ini
# Storage Directory and Retention Configuration
KYC_DATA_DIR=/var/data/kyc
KYC_EVIDENCE_RETENTION_DAYS=30
KYC_PURGE_MEDIA_ON_APPROVAL=false
```

- **`KYC_EVIDENCE_RETENTION_DAYS`**: Automatically purges raw media files older than the specified number of days while preserving the structured metadata, audit timestamps, and reason codes in PostgreSQL.
- **`KYC_PURGE_MEDIA_ON_APPROVAL`**: When set to `true`, immediately deletes raw video and audio files once a verification evaluates to `approved`, retaining only the numerical embeddings and metadata logs.
