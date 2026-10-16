# Project Context Brief: Identity Verification Service (UNCLONE Track 02)

Paste this into any LLM before asking for help · Updated Oct 16, 2026 · Compiled from the team's planning chat

## 1. Instructions for the AI reading this

- You are helping a student hackathon team build the project below in roughly 24 hours. Be direct and practical, casual tone, no fluff.
- Treat section 4 (decisions) as settled unless the team reopens them.
- Items marked (unverified) come from general knowledge, not checked documentation. Verify before relying on them.
- Prefer free and open-source tools and pretrained models. Do not suggest training large models from scratch.
- Keep every design buildable in the time left, and say what to cut.
- Never suggest auto-rejecting people. The system flags, and a human decides.
- Ask at most one clarifying question at a time.
- When you write code, keep modules small and swappable, and follow the check-result contract in section 6.

## 2. Hackathon and problem

- **Event:** UNCLONE hackathon. The team chose **Track 02: Unclone Identity**. Track text: prove who is really on the other end in KYC, hiring, exams and remote work, when anyone can be cloned.
- **Other tracks (not chosen):** Track 01 Unclone Finance (protect banks, NBFCs, insurers, UPI users from voice fraud) and Track 03 Unclone Agents (AI voice agents that verify the caller).
- **Form question the team had to answer:** one use case of deepfake detection or speaker verification the team will build.
- **Sponsor API:** the hackathon company provides Detectif.ai (voice deepfake detection and speaker verification). The team is using it.
- **Time:** about 24 hours to build and demo. Team size, GPU access and demo hardware are not yet confirmed.
- **Judging angle the team believes in:** a live demo that lands in seconds, honest measured numbers on unseen attacks, and a clear business story.

## 3. The product

A **B2B identity-verification service** that any company can plug in for KYC. Later it can extend to interview fraud, exams and remote work using the same engine.

**Pattern (Stripe Identity or Onfido style):** the customer's backend calls our API to create a verification session. Their end user completes a flow on our hosted page. The result comes back by signed webhook. A dashboard lets the customer review flagged cases and tune policy.

**Four pieces, all web:**

1. **API (FastAPI):** creates sessions, runs checks, decides, sends webhooks.
2. **Hosted verification page:** mobile-first React page with camera, mic, ID upload and challenges. Phone-first via QR code from desktop.
3. **Dashboard:** sessions, review queue, evidence, per-tenant policy settings.
4. **Demo client site:** a fake fintech signup page that integrates the API in about 10 lines. This proves it is a service.

## 4. Decisions made so far

- Chose Track 02 (Identity). Went from voice-only to **face + voice (multimodal)**.
- Explored an **interview-fraud overlay** on Zoom, Teams and Meet (see section 12). Browser extension rejected because it only covers Meet in the browser. A desktop app is the way for the overlay. That idea is now a roadmap or second mode.
- **Current focus: KYC as a service**, demoable at the hackathon.
- **Web, not native app,** for the demo. Phone-first via QR to harden against virtual cameras and casting.
- **AI voice check and speaker verification use Detectif.ai.** Do not self-host anti-spoof models for the demo.
- **Video deepfake detection is deferred to the end.** Until then it returns not\_sure.
- Phone OTP is built behind a swappable provider with a mock mode, because SMS in India needs DLT registration.
- Keep all attack testing to consenting teammates and sample IDs. No real government IDs.

## 5. KYC verification targets (the team's list)

1. Face should match the ID proof.
2. Check if the voice is AI-generated.
3. Video deepfake detection (last).
4. Audio parser: verify that spoken details match the ID details.
5. Phone and email OTP verification.
6. Spontaneous text (random challenge sentence) with no screen-casting options.

## 6. Architecture and contracts

**Pipeline:** hosted flow app, then sessions service, job queue, check workers, decision engine (reads the tenant policy), webhook dispatcher. Providers such as Detectif sit behind adapter interfaces so they can be swapped.

**Multi-tenancy:** tenant\_id on every row, hashed API keys per tenant, rate limits, per-tenant policy JSON, evidence stored encrypted with expiring signed URLs.

### 6.1 API

| Call | Purpose |
| --- | --- |
| POST /v1/verifications | Create a session: reference\_id, checks, policy, callback\_url, redirect\_url. Returns session id and flow URL |
| GET /v1/verifications/{id} | Status, per-check results, reasons |
| Webhook verification.completed | Signed with HMAC plus timestamp, retried. Status: approved, needs\_review or rejected |
| GET /v1/verifications/{id}/evidence | Expiring signed URLs |
| DELETE /v1/verifications/{id} | Data deletion |
| Policies | Per-tenant thresholds and which checks run (strict vs lenient) |

Use an Idempotency-Key header on creates.

### 6.2 Check-result contract (every check returns this)

Fields: name, status (pass, fail, uncertain, skipped), score (0 to 1), confidence (0 to 1), reason (short human-readable text), details (optional object). The decision engine only reads this shape, so any check can be added or replaced without touching the rest.

### 6.3 Decision engine

- Reads the tenant policy JSON (which checks are required, thresholds, how many uncertain results are tolerated).
- Outputs approved, needs\_review or rejected-recommended, always with reasons.
- A low-quality signal is marked uncertain and excluded, never treated as a pass.
- Start rule-based with hysteresis. Fit a calibrated fusion model (logistic regression) later if time allows.

## 7. Check modules

| Check | Tool | Notes |
| --- | --- | --- |
| Face detection | SCRFD (InsightFace) | Largest and highest-confidence face on the ID image |
| Face match to ID | ArcFace via InsightFace buffalo\_l | Weights are research and non-commercial only, so note it in the README. Calibrate thresholds on teammates' ID-photo vs selfie pairs and report false-accept and false-reject rates. AdaFace is an optional low-quality-image alternative (unverified) |
| ID OCR | PaddleOCR or EasyOCR | Extract name, date of birth, ID number, photo |
| Liveness | Random head turn and hand-wave challenges, face-detector dropout and embedding discontinuity | The occlusion idea is a hypothesis to validate with our own attacks |
| AI voice check | Detectif.ai /v1/deepfake/detect | Signal, not verdict |
| Voice consistency | Detectif.ai speaker enroll and verify | No prior voiceprint exists in KYC, so only within-session consistency |
| Spoken details vs ID | faster-whisper, rapidfuzz, number and date normalization | Ask fixed questions (date of birth, last 4 digits of ID). Do not parse free speech. Pass the OCR name as a prompt to bias spelling |
| Email OTP | Any free-tier email API or SMTP | 6 digits, hashed, expires in about 5 minutes, 3 to 5 attempts, rate limited, single use |
| Phone OTP | Pluggable provider with a mock mode | India SMS needs DLT registration, so do not depend on it in 24 hours |
| Source and device checks | Browser APIs | See section 9 |
| Video deepfake | CLIP ViT-L/14 with light tuning (planned) | Deferred. Returns not\_sure until built |

Never ask users to read OTPs aloud. Use a separate random challenge code for spoken liveness.

## 8. Detectif.ai API facts (read from their docs)

- Base URL: https://platform.detectif.ai/v1. Auth: Bearer API key. **Call it from the backend only.**
- Endpoints: POST /v1/deepfake/detect, POST /v1/speakers/enroll, POST /v1/speakers/verify, GET and DELETE speakers, GET /v1/operations/{id}, POST /v1/operations/{id}/feedback, GET /v1/credits, GET /v1/usage, GET /v1/health.
- Upload-based (multipart field file), not streaming. Formats: WAV, MP3, M4A, FLAC, OGG, WebM. Up to 100 MB.
- Deepfake result: verdict real, fake or not\_sure, plus score 0 to 1 and threshold. Treat as a signal, not proof.
- Clip length is inconsistent in their docs: the quickstart says longer than 4 seconds, the limits page says 0.5 to 120 seconds. Test a short clip.
- Enroll: 15 to 60 seconds with at least 10 seconds of speech. Verify: 3 to 60 seconds with at least 2 seconds of speech. Up to 5 enrolled recordings per speaker.
- Tuned for English. Phone-quality audio is less reliable.
- 429 or 503 responses include Retry-After. Retry with the same Idempotency-Key.
- Voiceprints are stored on their side. Check their Privacy page and add it to the consent text.
- Pricing was not found. The API is credit-based. Ask organizers for hackathon credits and keep calls low.
- Wire the false-alarm button to the feedback endpoint.

## 9. Blocking casting and injection (honest stance)

A browser cannot truly block Chromecast, AirPlay, remote desktop, a second device or a virtual camera. The goal is to make it hard and detectable, and pitch it as injection-resistant by design.

- Never call screen-capture APIs. Require fullscreen.
- Flag tab or window focus loss (visibilitychange, blur) and extended displays (screen.isExtended in Chrome).
- Flag virtual-camera device names (OBS, ManyCam, DroidCam, Iriun and similar) and odd camera settings. A generically named virtual cam can evade this.
- Strongest defense is design: random, timed, spontaneous challenges that a replayed or pre-recorded feed cannot answer.
- Phone-first via QR code makes virtual-camera injection much harder.
- Native option (roadmap): Android FLAG\_SECURE and Play Integrity (default 10K requests per app per day) harden screen capture and device integrity. A desktop app can scan for known tools. Nothing is unbreakable: rooted or emulated devices and a camera filming a screen still get through.

## 10. Compliance notes (India, not legal advice)

- RBI V-CIP (video KYC) is not self-serve. It needs a live trained officer, liveness, face match, geo-tagging, encrypted recording and an audit trail, and it must run through the regulated entity's own website or app.
- So position the product either as the **deepfake and identity-risk layer assisting an officer during V-CIP**, or as automated checks for non-V-CIP onboarding and other industries (hiring, gig platforms, exams). White-label or embedded SDK matters more than redirecting users to our domain.
- Aadhaar: only permitted methods such as OTP e-KYC and offline verification. Do not store raw Aadhaar numbers.
- Face, voice and ID data is sensitive: consent, retention limits, deletion, India data residency, DPDP Act. Get legal review before any real deployment.
- Fairness: poor lighting, cameras, accents and disabilities cause false positives. Use quality gates, soft wording ('needs verification'), human review, and report false-alarm rates.

## 11. 24-hour build plan

**Build order**

1. **Walking skeleton first (hours 0 to 3):** demo client clicks Verify, API creates a session, flow page opens, a fake check approves, signed webhook hits the client, client shows Approved. No ML yet.
2. Real checks one at a time: email OTP, ID upload and OCR, face match, liveness challenge, Detectif voice check and spoken-details match, source checks.
3. Decision engine with per-tenant policy JSON (strict vs lenient).
4. Dashboard: sessions, evidence, review buttons, policy toggle.
5. Video deepfake last.

**Stack:** FastAPI, SQLite (Postgres only if time), simple background worker, one React or Next.js app for the flow page and dashboard, HTTPS tunnel (ngrok or cloudflared) so phones can use the camera, everything on a laptop with model weights cached beforehand.

**Roles (merge if fewer people):** A API, database, decision engine, webhooks. B verification page. C ML checks. D dashboard, demo client, slides.

**Demo script:** show the 10-line client integration; a real person verifies from a phone via QR and the client shows approved; attack run (different person or cloned voice) fails and the dashboard shows why; flip policy lenient to strict; show results slide with error rates. Record a backup video by hour 20.

**Evaluation to report:** per-check error rates, results on clean vs compressed audio, per-attack detection at a fixed false-alarm rate, false alarms on genuine sessions, time to verdict.

## 12. Earlier idea kept for roadmap: interview-fraud overlay

A desktop overlay (Electron plus Python backend) on Zoom, Teams and Meet for interviewers. It captures the candidate's video tile and system audio, enrolls face and voice at round 1, and checks later rounds for person mismatch, voice mismatch or clone, face-swap deepfakes (with a hand-wave challenge), an off-camera helper, looped video, and duplicate candidates across applications. Typing sounds and gaze are soft, low-reliability flags. Zoom Realtime Media Streams is the official bot-free route but needs a paid developer plan. Same engine as the KYC service, with a different policy layer.

## 13. Open questions

- Team size and who has frontend, ML and backend experience?
- GPU access? Demo OS and hardware?
- Detectif.ai credits and pricing, and whether organizers offer an SMS sandbox?
- Judging rubric weights (technical depth vs business impact vs demo)?
- Language of spoken challenges (Detectif is tuned for English)?

## 14. References

- Detectif.ai docs: platform.detectif.ai/docs/ and platform.detectif.ai/docs/api/
- InsightFace: github.com/deepinsight/insightface (models are non-commercial unless licensed)
- CLIP deepfake detection (Yermakov et al.): arxiv.org/abs/2503.19683
- Zoom Realtime Media Streams: developers.zoom.us/blog/realtime-media-streams/
- RBI KYC Master Direction and V-CIP amendments: rbi.org.in
