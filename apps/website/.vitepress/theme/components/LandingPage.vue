<template>
  <div class="landing-page">
    <!-- Hero Section -->
    <section class="hero-section">
      <div class="site-container">
        <div class="hero-brand">
          <img src="/images/ryouu-suite-logo-light.png" alt="RyouU Suite" class="hero-brand-logo light-only" width="220" height="147" />
          <img src="/images/ryouu-suite-logo-dark.png" alt="RyouU Suite" class="hero-brand-logo dark-only" width="220" height="147" />
        </div>
        <div class="badge-pill">
          <span class="badge-dot"></span>
          RyouU Identity &amp; Live Interview Suite
        </div>
        <h1 class="hero-title">
          Know who is really on the other end, even when faces and voices can be cloned
        </h1>
        <p class="hero-subtitle">
          Layered, server-enforced identity verification and live interview monitoring. The system flags anomalies and explains; your human reviewers decide.
        </p>

        <div class="hero-actions">
          <a href="/overview" class="btn btn-primary">Read the Docs</a>
          <a href="#demo" class="btn btn-secondary">Watch Demo</a>
        </div>

        <!-- Checkout-like Integration Code Snippet -->
        <div class="code-hero-card">
          <div class="code-hero-header">
            <span>Backend Session Minting &amp; SDK Embed</span>
            <div class="code-hero-dots">
              <div class="code-hero-dot"></div>
              <div class="code-hero-dot"></div>
              <div class="code-hero-dot"></div>
            </div>
          </div>
          <div class="code-hero-body">
<pre style="margin: 0; max-width: 100%; overflow-x: auto;"><code><span style="color:#64748B;"># Integrates cleanly into your backend like a payment checkout:</span>
<span style="color:#93C5FD;">from</span> unclone_kyc <span style="color:#93C5FD;">import</span> Client

client = Client(api_key=<span style="color:#86EFAC;">"kyc_live_..."</span>)
session = client.create_verification(
    reference_id=<span style="color:#86EFAC;">"usr_9402"</span>,
    expected={"name": <span style="color:#86EFAC;">"Alex Morgan"</span>, "dob": <span style="color:#86EFAC;">"1995-08-20"</span>},
    policy=<span style="color:#86EFAC;">"strict"</span>
)

<span style="color:#64748B;"># Pass session.flow_url to your React Native or Android client</span>
<span style="color:#93C5FD;">return</span> {"flow_url": session.flow_url}</code></pre>
          </div>
        </div>
      </div>
    </section>

    <!-- Two Core Products Section -->
    <section class="section" id="products">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Two Integrated Products</div>
          <h2 class="section-title">Built for onboarding and <span class="nowrap">high-stakes</span> remote conversations</h2>
          <p class="section-description">
            Use the asynchronous KYC SDK for customer onboarding, the desktop overlay for remote technical interviews, or run both from a unified self-hosted instance.
          </p>
        </div>

        <div class="product-grid">
          <!-- KYC SDK Card -->
          <div class="product-card">
            <div class="product-badge">
              <span class="status-chip stable">Self-Serve KYC SDK</span>
            </div>
            <h3 class="product-title">Identity Verification SDK</h3>
            <p class="product-desc">
              Hosted multi-step web flow with document OCR, biometric face match, and challenge-based active liveness. Runs seamlessly in mobile WebViews.
            </p>
            <div class="product-action">
              <a href="/overview" class="product-link">
                <span>Explore SDK architecture</span>
                <span class="product-link-arrow">→</span>
              </a>
            </div>
            <div class="product-screenshot-frame">
              <img src="/images/ui/hosted_flow_liveness.png" alt="RyouU Hosted Flow Active Liveness Screen" width="600" height="375" loading="lazy" />
            </div>
          </div>

          <!-- Interview Overlay Card -->
          <div class="product-card">
            <div class="product-badge">
              <span class="status-chip review">Live Interview Overlay</span>
            </div>
            <h3 class="product-title">Interview Integrity Panel</h3>
            <p class="product-desc">
              Desktop assistant for interviewers that monitors candidate video clips and audio streams in real-time, matching voiceprints against enrolled KYC references.
            </p>
            <div class="product-action">
              <a href="/overlay/installation" class="product-link">
                <span>Explore overlay setup</span>
                <span class="product-link-arrow">→</span>
              </a>
            </div>
            <div class="product-screenshot-frame">
              <img src="/images/ui/overlay_monitoring.png" alt="RyouU Desktop Overlay Live Monitoring Screen" width="600" height="375" loading="lazy" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- How It Works (3 Steps) -->
    <section class="section">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Architecture Workflow</div>
          <h2 class="section-title">How verification works in three steps</h2>
          <p class="section-description">Zero secret API keys in client apps. Your server creates sessions and evaluates cryptographically signed webhooks.</p>
        </div>

        <div class="steps-grid">
          <div class="step-card">
            <div class="step-num">1</div>
            <h3 class="step-title">Your backend creates a session</h3>
            <p class="step-desc">
              Your server calls <code>POST /v1/verifications</code> with the user's expected profile and receives a short-lived, scoped <code>flow_url</code>.
            </p>
          </div>

          <div class="step-card">
            <div class="step-num">2</div>
            <h3 class="step-title">Candidate completes hosted flow</h3>
            <p class="step-desc">
              The candidate uploads ID document photos, completes active biometric head turns and blinks, and answers spontaneous challenge phrases.
            </p>
          </div>

          <div class="step-card">
            <div class="step-num">3</div>
            <h3 class="step-title">You receive signed webhook</h3>
            <p class="step-desc">
              RyouU emits an HMAC-SHA256 signed event. Your backend verifies the signature, fetches the verdict, and applies your business logic.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- What It Checks (Honest Catalog) -->
    <section class="section">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Verification Signals</div>
          <h2 class="section-title">What it checks, in plain language</h2>
          <p class="section-description">
            Signals are categorized by production maturity. Weak signals never issue automated denials; they flag for human review.
          </p>
        </div>

        <div class="table-container">
          <table class="catalog-table">
            <thead>
              <tr>
                <th>Check / Signal</th>
                <th>Maturity</th>
                <th>Description &amp; Underlying Tech</th>
                <th>Decision Impact</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div class="catalog-name">ID Document Consistency</div>
                  <div class="catalog-tech">RapidOCR (ONNX) + Fuzzy Match</div>
                </td>
                <td><span class="status-chip stable">Stable</span></td>
                <td>Extracts name, DOB, and ID number from government documents. Compares against expected inputs.</td>
                <td><strong>Hard Gate</strong> (Can reject if mismatched)</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Face Match (ID vs Selfie)</div>
                  <div class="catalog-tech">InsightFace ArcFace (512-dim)</div>
                </td>
                <td><span class="status-chip stable">Stable</span></td>
                <td>Computes cosine similarity between document photo face crop and active live selfie.</td>
                <td><strong>Hard Gate</strong> (Can reject if cosine &lt; 0.25)</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Active Biometric Liveness</div>
                  <div class="catalog-tech">MediaPipe 52 Blendshapes</div>
                </td>
                <td><span class="status-chip stable">Stable</span></td>
                <td>Verifies voluntary eye blinks and directed 3D head yaw rotation during capture session.</td>
                <td>Flags to <strong>needs_review</strong> if unfulfilled</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Passive Anti-Spoofing (PAD)</div>
                  <div class="catalog-tech">MiniFASNetV2 (ONNX)</div>
                </td>
                <td><span class="status-chip beta">Beta</span></td>
                <td>Detects physical presentation attacks, paper printouts, and digital screen replays.</td>
                <td>Flags to <strong>needs_review</strong> (Uncalibrated)</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Visual Video Deepfake</div>
                  <div class="catalog-tech">ViT Classifier / CLIP ViT-L/14</div>
                </td>
                <td><span class="status-chip beta">Beta</span></td>
                <td>Multi-frame synthetic face manipulation detection across recorded video clips.</td>
                <td>Flags to <strong>needs_review</strong> (Weak signal)</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Spontaneous Lip Sync</div>
                  <div class="catalog-tech">SyncNet + faster-whisper</div>
                </td>
                <td><span class="status-chip experimental">Experimental</span></td>
                <td>Aligns acoustic speech envelope with mouth bounding box RMS displacement.</td>
                <td>Flags to <strong>needs_review</strong> (Weak signal)</td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Voice AI &amp; Clone Detection</div>
                  <div class="catalog-tech">Detectif.ai Cloud API (Aletheia)</div>
                </td>
                <td><span class="status-chip beta">Beta</span></td>
                <td>Detects synthetic text-to-speech audio and voice cloning. Best calibrated in English.</td>
                <td>Flags to <strong>needs_review</strong></td>
              </tr>
              <tr>
                <td>
                  <div class="catalog-name">Speaker Verification</div>
                  <div class="catalog-tech">Detectif.ai Eidos / Supabase Audio</div>
                </td>
                <td><span class="status-chip beta">Beta</span></td>
                <td>Compares interview audio stream against reference voice enrolled during initial KYC.</td>
                <td>Flags to <strong>needs_review</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- Human In The Loop Decision States -->
    <section class="section">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Server-Enforced Decisions</div>
          <h2 class="section-title">Human-in-the-loop: recommendations, not blind bans</h2>
          <p class="section-description">
            The server categorizes verifications into three explicit recommendation states. Status <code>completed</code> only means processing finished; verdict is evaluated from <code>final_decision ?? decision</code>.
          </p>
        </div>

        <div class="decision-grid">
          <div class="decision-card approved">
            <div class="decision-header">
              <span class="decision-name">approved</span>
              <span class="status-chip approved">Success</span>
            </div>
            <div class="decision-rule">
              All hard gates passed cleanly, ID details matched, face cosine similarity passed threshold, and no anomalous deepfake or anti-spoof flags were raised.
            </div>
          </div>

          <div class="decision-card review">
            <div class="decision-header">
              <span class="decision-name">needs_review</span>
              <span class="status-chip review">Manual Review</span>
            </div>
            <div class="decision-rule">
              Neither success nor failure. Raised when any soft AI signal (anti-spoof, lip-sync, deepfake, scene switch) indicates uncertainty. Your human compliance officer inspects evidence and decides.
            </div>
          </div>

          <div class="decision-card rejected">
            <div class="decision-header">
              <span class="decision-name">rejected_recommended</span>
              <span class="status-chip flagged">Failed Gate</span>
            </div>
            <div class="decision-rule">
              Autonomous denial recommendation triggered <em>only</em> by hard, objective mismatches: name mismatch, DOB mismatch, failed SMS OTP, or face similarity below 0.25.
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Deployment & Self-Hosting -->
    <section class="section">
      <div class="site-container">
        <div class="deploy-box">
          <div>
            <div class="section-label">Deployment Flexibility</div>
            <h2 style="font-size: 26px; font-weight: 800; margin: 0 0 16px; color: var(--vp-c-text-1);">Self-host with Docker or run in the cloud</h2>
            <p style="font-size: 15px; color: var(--vp-c-text-3); line-height: 1.6; margin: 0 0 20px;">
              Deploy RyouU KYC and the interview backend on your own infrastructure with a single Docker command. Store biometric evidence in your own Postgres database and S3-compatible buckets.
            </p>
            <ul style="padding-left: 20px; font-size: 14px; color: var(--vp-c-text-2); display: flex; flex-direction: column; gap: 8px;">
              <li>Zero egress of biometric data unless external voice APIs are enabled</li>
              <li>Run CPU-only ONNX pipelines without requiring dedicated GPU clusters</li>
              <li>Ready for Kubernetes with health and readiness probes (<code>/healthz</code>, <code>/readyz</code>)</li>
            </ul>
          </div>
          <div>
            <div class="code-hero-card" style="margin: 0;">
              <div class="code-hero-header">
                <span>Docker Compose Quickstart</span>
              </div>
              <div class="code-hero-body" style="overflow-x: auto; max-width: 100%;">
<pre style="margin: 0; max-width: 100%; overflow-x: auto;"><code><span style="color:#64748B;"># Clone repository and launch verified container</span>
git clone https://github.com/wequgy/RyouU.git
cd RyouU

<span style="color:#64748B;"># Start the KYC service and postgres</span>
docker compose up -d

<span style="color:#64748B;"># Check ready state</span>
curl http://localhost:8000/readyz
<span style="color:#86EFAC;">{"status": "ready", "models_loaded": true}</span></code></pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Security & Privacy Safeguards -->
    <section class="section">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Security &amp; Privacy</div>
          <h2 class="section-title">Verified technical safeguards</h2>
          <p class="section-description">Only what the code actually enforces. No false claims.</p>
        </div>

        <div class="steps-grid">
          <div class="step-card">
            <h3 class="step-title">Scoped API Keys</h3>
            <p class="step-desc">
              Client secrets are never embedded in mobile apps. Customer backends issue short-lived session tokens for WebView flows.
            </p>
          </div>
          <div class="step-card">
            <h3 class="step-title">HMAC-SHA256 Webhooks</h3>
            <p class="step-desc">
              Outbound webhooks carry timestamped signatures with a configurable 300-second replay tolerance window.
            </p>
          </div>
          <div class="step-card">
            <h3 class="step-title">Encrypted Evidence &amp; Retention</h3>
            <p class="step-desc">
              Biometric crops and audio files are stored locally or in customer-controlled object stores with configurable retention pruning.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Demo Video Slot Placeholder -->
    <section class="section" id="demo">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Product Demo</div>
          <h2 class="section-title">See RyouU in action</h2>
          <p class="section-description">A walkthrough of the hosted verification flow and live interview overlay.</p>
        </div>

        <div class="video-slot">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polygon points="10 8 16 12 10 16 10 8"></polygon>
          </svg>
          <div style="font-weight: 700; color: #FFFFFF;">Demo Video Coming Soon</div>
          <div style="font-size: 13px; max-width: 440px;">
            <!-- TODO: Provide final production walkthrough video URL -->
            We are finalizing the official high-resolution walkthrough. In the meantime, explore the step-by-step interactive documentation.
          </div>
        </div>
      </div>
    </section>

    <!-- Limits & Responsibilities -->
    <section class="section">
      <div class="site-container">
        <div class="section-header">
          <div class="section-label">Limits &amp; Legal Notice</div>
          <h2 class="section-title">Compliance and your responsibilities</h2>
          <p class="section-description">Plain statements on regulatory scope, model limitations, and licensing.</p>
        </div>

        <div class="faq-grid">
          <div class="faq-item">
            <h3 class="faq-q">Does RyouU certify compliance with RBI V-CIP, GDPR, or DPDP?</h3>
            <p class="faq-a">
              <strong>No.</strong> RyouU provides technical building blocks (biometric face matching, liveness tracking, and signed audit trails). Customers must conduct their own legal and regulatory reviews to determine whether their deployment satisfies applicable local regulations.
            </p>
          </div>

          <div class="faq-item">
            <h3 class="faq-q">Are deepfake, anti-spoofing, and lip-sync signals 100% reliable?</h3>
            <p class="faq-a">
              <strong>No.</strong> Deepfake, liveness, and lip-sync classifications are probabilistic soft signals. Thresholds remain uncalibrated on production webcam distributions until evaluated on your domain data. They are designed exclusively to trigger human review, never automated rejections.
            </p>
          </div>

          <div class="faq-item">
            <h3 class="faq-q">What are the licensing terms for InsightFace?</h3>
            <p class="faq-a">
              Pretrained weights for InsightFace (<code>buffalo_l</code>) are restricted to non-commercial academic research and evaluation. Commercial production deployments must substitute with commercially licensed weights or commercial face matching APIs. All other local models (MediaPipe, MiniFASNetV2, RapidOCR, Whisper) use permissive Apache 2.0 or MIT licenses.
            </p>
          </div>

          <div class="faq-item">
            <h3 class="faq-q">How does Voice AI detection work?</h3>
            <p class="faq-a">
              Synthetic voice detection and speaker verification rely on the Detectif.ai Cloud API (Aletheia and Eidos models). Performance is highest on English-language audio. Phone OTP verification requires customer-configured SMS credentials (Twilio or Fast2SMS).
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// Vue 3 Composition API component for RyouU Landing Page
</script>

<style scoped>
.landing-page {
  width: 100%;
  overflow-x: hidden;
  max-width: 100vw;
}

/* Hero Section */
.hero-section {
  padding: 64px 0 56px;
  text-align: center;
  background: radial-gradient(circle at 50% 0%, var(--primary-light) 0%, transparent 60%);
}
.dark .hero-section {
  background: radial-gradient(circle at 50% 0%, rgba(101, 163, 13, 0.12) 0%, transparent 60%);
}

.badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--surface-card);
  border: 1px solid var(--primary-border);
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}
.badge-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
}

.hero-title {
  font-size: clamp(30px, 5vw, 52px);
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.03em;
  color: var(--vp-c-text-1);
  max-width: 860px;
  margin: 0 auto 20px;
}
.hero-subtitle {
  font-size: clamp(15px, 2.5vw, 18px);
  color: var(--vp-c-text-3);
  max-width: 680px;
  margin: 0 auto 32px;
  font-weight: 400;
}
.hero-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 48px;
}

/* Code Snippet Card */
.code-hero-card {
  width: 100%;
  max-width: 680px;
  min-width: 0;
  margin: 0 auto;
  background: var(--surface-video);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  text-align: left;
  overflow: hidden;
  box-sizing: border-box;
}
.code-hero-header {
  padding: 12px 18px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #94A3B8;
  font-family: var(--font-mono);
}
.code-hero-dots {
  display: flex;
  gap: 6px;
}
.code-hero-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
}
.code-hero-body {
  padding: 20px 24px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  color: #E2E8F0;
  overflow-x: auto;
  max-width: 100%;
  box-sizing: border-box;
}

/* Section Common */
.section {
  padding: 88px 0;
  border-top: 1px solid var(--border);
}
.section-header {
  text-align: center;
  max-width: 720px;
  margin: 0 auto 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.section-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-c-brand-1);
  background: var(--vp-c-brand-soft);
  border: 1px solid var(--primary-border);
  padding: 5px 14px;
  border-radius: var(--radius-pill);
  margin-bottom: 18px;
}
.nowrap {
  white-space: nowrap;
}
.section-title {
  font-size: clamp(26px, 3.4vw, 38px);
  font-weight: 800;
  line-height: 1.32;
  letter-spacing: -0.012em;
  text-wrap: balance;
  margin: 0 0 16px;
  color: var(--vp-c-text-1);
  max-width: 760px;
}
.section-description {
  font-size: 16px;
  line-height: 1.65;
  color: var(--vp-c-text-3);
  margin: 0 auto;
  max-width: 620px;
  text-wrap: pretty;
}

/* Container */
.site-container {
  width: 100%;
  max-width: var(--container-max);
  margin: 0 auto;
  padding: 0 24px;
  box-sizing: border-box;
}

/* Hero Brand Logo */
.hero-brand {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 24px;
}
.hero-brand-logo {
  height: 84px;
  width: auto;
  object-fit: contain;
  transition: transform var(--transition-fast);
}
.hero-brand-logo:hover {
  transform: scale(1.03);
}

.dark-only {
  display: none !important;
}
.light-only {
  display: block !important;
}
:root.dark .dark-only,
html.dark .dark-only {
  display: block !important;
}
:root.dark .light-only,
html.dark .light-only {
  display: none !important;
}

/* Product Cards */
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 32px;
}
.product-card {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.product-card:hover {
  border-color: var(--border-card-hover);
  box-shadow: var(--shadow-card-hover);
}
.product-badge {
  align-self: flex-start;
  margin-bottom: 16px;
}
.product-title {
  font-size: 21px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: -0.01em;
  color: var(--vp-c-text-1);
  margin: 0 0 10px;
}
.product-desc {
  font-size: 14.5px;
  line-height: 1.62;
  color: var(--vp-c-text-3);
  margin: 0 0 16px;
  min-height: 48px;
  text-wrap: pretty;
}
.product-action {
  margin-bottom: 20px;
}
.product-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--vp-c-brand-1);
  text-decoration: none;
  transition: gap var(--transition-fast);
}
.product-link:hover {
  color: var(--vp-c-brand-2);
  gap: 10px;
}
.product-screenshot-frame {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface-card-sub);
  height: 320px;
  position: relative;
  box-shadow: var(--shadow-sm);
  margin-top: 0;
}
.product-screenshot-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top center;
  display: block;
  transition: transform 0.3s ease;
}
.product-card:hover .product-screenshot-frame img {
  transform: scale(1.02);
}
.product-screenshot-frame::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 50px;
  background: linear-gradient(to bottom, transparent 0%, rgba(15, 23, 42, 0.45) 100%);
  pointer-events: none;
}
:root:not(.dark) .product-screenshot-frame::after {
  background: linear-gradient(to bottom, transparent 0%, rgba(255, 255, 255, 0.65) 100%);
}

/* 3-Step Grid */
.steps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
}
.step-card {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 28px;
}
.step-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 14px;
  margin-bottom: 16px;
}
.step-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--vp-c-text-1);
  margin: 0 0 8px;
}
.step-desc {
  font-size: 14px;
  color: var(--vp-c-text-3);
  margin: 0;
  line-height: 1.6;
}

/* Table Container & Table */
.table-container {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  box-sizing: border-box;
  display: block;
}
.catalog-table {
  width: 100%;
  min-width: 500px;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-card);
}
.catalog-table th, .catalog-table td {
  padding: 16px 20px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.catalog-table th {
  background: var(--surface-card-sub);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--vp-c-text-3);
}
.catalog-name {
  font-weight: 700;
  color: var(--vp-c-text-1);
  font-size: 14px;
}
.catalog-tech {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-dim);
}

/* Decisions */
.decision-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}
.decision-card {
  border-radius: var(--radius-md);
  padding: 24px;
  border: 1px solid;
}
.decision-card.approved {
  background: var(--signal-clear-bg);
  border-color: var(--signal-clear-border);
}
.decision-card.review {
  background: var(--signal-caution-bg);
  border-color: var(--signal-caution-border);
}
.decision-card.rejected {
  background: var(--signal-flag-bg);
  border-color: var(--signal-flag-border);
}
.decision-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.decision-name {
  font-weight: 800;
  font-size: 16px;
}
.decision-card.approved .decision-name { color: var(--signal-clear); }
.decision-card.review .decision-name { color: var(--signal-caution); }
.decision-card.rejected .decision-name { color: var(--signal-flag); }
.decision-rule {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-sub);
}

/* Deploy Box */
.deploy-box {
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 32px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  align-items: center;
}
@media (max-width: 768px) {
  .deploy-box {
    grid-template-columns: 1fr;
    padding: 20px;
    gap: 24px;
  }
}

/* FAQ */
.faq-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  max-width: 820px;
  margin: 0 auto;
}
.faq-item {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px 24px;
}
.faq-q {
  font-weight: 700;
  font-size: 16px;
  color: var(--vp-c-text-1);
  margin: 0 0 8px;
}
.faq-a {
  font-size: 14px;
  color: var(--vp-c-text-3);
  margin: 0;
  line-height: 1.6;
}

/* Video Slot */
.video-slot {
  max-width: 820px;
  margin: 0 auto;
  aspect-ratio: 16 / 9;
  background: var(--surface-video);
  border: 1px dashed var(--border-card-hover);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
  gap: 12px;
  text-align: center;
  padding: 24px;
}

@media (max-width: 640px) {
  .site-container {
    padding: 0 14px;
  }
  .code-hero-body {
    padding: 14px 16px;
    font-size: 11.5px;
  }
  .product-card {
    padding: 20px;
  }
}
</style>
