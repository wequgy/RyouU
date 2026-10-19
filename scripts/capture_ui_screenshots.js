// @ts-check
/**
 * Automated UI Screenshot Capture Script for RyouU Documentation & Marketing Site.
 * Captures the REAL, production UI states of both:
 * 1. KYC Hosted Verification Flow (flow.html) in Document, Liveness, and Verdict states.
 * 2. Interview Integrity Desktop Overlay (index.html) in Idle, Monitoring, Needs Attention, and Unavailable states.
 */

const { chromium } = require("../apps/overlay/node_modules/@playwright/test");
const path = require("path");
const fs = require("fs");

const OUT_DIR = path.resolve(__dirname, "../apps/website/public/images/ui");
const FLOW_HTML_PATH = "file://" + path.resolve(__dirname, "../services/api/app/static/flow.html").replace(/\\/g, "/");
const OVERLAY_HTML_PATH = "file://" + path.resolve(__dirname, "../apps/overlay/src/renderer/index.html").replace(/\\/g, "/");

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log(`[Capture] Launching Playwright Chromium...`);
  const browser = await chromium.launch({ headless: true });

  try {
    // -------------------------------------------------------------
    // PART A: KYC Hosted Flow Screenshots (Mobile Viewport: 440 x 860)
    // -------------------------------------------------------------
    const kycContext = await browser.newContext({
      viewport: { width: 440, height: 860 },
      deviceScaleFactor: 2,
    });
    const kycPage = await kycContext.newPage();

    // Mock API & local storage / URL search params for flow
    await kycPage.addInitScript(() => {
      window.sessionStorage.setItem("kyc_flow_token", "flow_tok_sample");
    });

    console.log(`[Capture] Navigating to Hosted Flow (${FLOW_HTML_PATH})...`);
    await kycPage.goto(FLOW_HTML_PATH + "?token=flow_tok_demo_123", { waitUntil: "domcontentloaded" });

    // Ensure mock flow container renders
    await kycPage.evaluate(() => {
      // @ts-ignore
      if (typeof renderStepIdGate === "function") {
        // @ts-ignore
        renderStepIdGate();
      }
    });
    await kycPage.waitForTimeout(300);

    const idGateOut = path.join(OUT_DIR, "hosted_flow_id_gate.png");
    await kycPage.screenshot({ path: idGateOut, fullPage: false });
    console.log(`[Capture] Saved: ${idGateOut}`);

    // State 2: Liveness Face Capture Step
    await kycPage.evaluate(() => {
      // @ts-ignore
      if (typeof renderStepSelfieGate === "function") {
        // @ts-ignore
        renderStepSelfieGate();
      }
    });
    await kycPage.waitForTimeout(300);
    const livenessOut = path.join(OUT_DIR, "hosted_flow_liveness.png");
    await kycPage.screenshot({ path: livenessOut, fullPage: false });
    console.log(`[Capture] Saved: ${livenessOut}`);

    // State 3: Final Decision / Verdict
    await kycPage.evaluate(() => {
      // @ts-ignore
      if (typeof renderFinalScreen === "function") {
        // @ts-ignore
        renderFinalScreen({
          status: "completed",
          final_decision: "approved",
          decision: "approved",
          checks_run: 6,
          checks_passed: 6,
        });
      }
    });
    await kycPage.waitForTimeout(300);
    const verdictOut = path.join(OUT_DIR, "hosted_flow_verdict.png");
    await kycPage.screenshot({ path: verdictOut, fullPage: false });
    console.log(`[Capture] Saved: ${verdictOut}`);
    await kycContext.close();

    // -------------------------------------------------------------
    // PART B: Live Interview Overlay HUD Screenshots (Desktop: 520 x 800)
    // -------------------------------------------------------------
    const overlayContext = await browser.newContext({
      viewport: { width: 520, height: 800 },
      deviceScaleFactor: 2,
    });
    const overlayPage = await overlayContext.newPage();

    await overlayPage.addInitScript(() => {
      window.ryouu = {
        detectMeetingApp: async () => ({ app: "Zoom" }),
        getLaunchSession: async () => null,
        connectInterview: async () => ({ success: true }),
        toggleCompact: () => {},
        closeApp: () => {},
        onMeetingAppDetected: () => {},
        onRegionSelected: () => {},
      };
    });

    console.log(`[Capture] Navigating to Interview Overlay (${OVERLAY_HTML_PATH})...`);
    await overlayPage.goto(OVERLAY_HTML_PATH, { waitUntil: "domcontentloaded" });
    await overlayPage.waitForTimeout(400);

    // State 1: IDLE State
    const idleOut = path.join(OUT_DIR, "overlay_idle.png");
    await overlayPage.screenshot({ path: idleOut });
    console.log(`[Capture] Saved: ${idleOut}`);

    // State 2: MONITORING ACTIVE (All signals passing naturally)
    await overlayPage.evaluate(() => {
      // @ts-ignore
      const allPassing = [
        { name: "interview_deepfake_video", status: "pass", reason: "Natural visual micro-motion", confidence: 0.94 },
        { name: "interview_voice_auth", status: "pass", reason: "Natural human acoustic timbre", confidence: 0.92 },
        { name: "interview_voice_id", status: "pass", reason: "Voice matches candidate baseline", confidence: 0.89 },
        { name: "interview_face_id", status: "pass", reason: "Face embedding matches enrolled candidate", confidence: 0.96 },
        { name: "interview_second_person", status: "pass", reason: "Single face present in stream", confidence: 0.99 },
        { name: "interview_lip_sync", status: "pass", reason: "Phoneme-viseme speech synchronised", confidence: 0.91 },
        { name: "interview_loop", status: "pass", reason: "Continuous physical camera feed", confidence: 0.95 },
      ];
      // @ts-ignore
      if (typeof renderResults === "function") {
        // @ts-ignore
        renderResults({ checks: allPassing }, "clear", "All 7 integrity signals verified. Continuous monitoring active.");
      }
      const timeProg = document.getElementById("timelineProgress");
      if (timeProg) timeProg.style.width = "48%";
      const timeStamp = document.getElementById("timelineTimestamp");
      if (timeStamp) timeStamp.textContent = "00:12 / 00:25";
    });
    await overlayPage.waitForTimeout(400);
    const monitoringOut = path.join(OUT_DIR, "overlay_monitoring.png");
    await overlayPage.screenshot({ path: monitoringOut });
    console.log(`[Capture] Saved: ${monitoringOut}`);

    // State 3: NEEDS ATTENTION / FLAGGED (Anomaly Detected)
    await overlayPage.evaluate(() => {
      // @ts-ignore
      const flaggedChecks = [
        { name: "interview_deepfake_video", status: "pass", reason: "Natural visual micro-motion", confidence: 0.91 },
        { name: "interview_voice_auth", status: "pass", reason: "Natural human acoustic timbre", confidence: 0.89 },
        { name: "interview_voice_id", status: "pass", reason: "Voice matches candidate baseline", confidence: 0.87 },
        { name: "interview_face_id", status: "pass", reason: "Face embedding matches enrolled candidate", confidence: 0.94 },
        { name: "interview_second_person", status: "pass", reason: "Single face present in stream", confidence: 0.98 },
        { name: "interview_lip_sync", status: "pass", reason: "Phoneme-viseme speech synchronised", confidence: 0.90 },
        { name: "interview_loop", status: "fail", reason: "OBS Virtual Camera software driver detected (video injection risk)", confidence: 0.99 },
      ];
      // @ts-ignore
      if (typeof renderResults === "function") {
        // @ts-ignore
        renderResults({ checks: flaggedChecks }, "flagged", "FLAGGED: Virtual camera detected. Ask candidate to switch to hardware camera.");
      }
    });
    await overlayPage.waitForTimeout(400);
    const attentionOut = path.join(OUT_DIR, "overlay_needs_attention.png");
    await overlayPage.screenshot({ path: attentionOut });
    console.log(`[Capture] Saved: ${attentionOut}`);

    // State 4: UNAVAILABLE / PARTIAL (Unenrolled or Missing API Key)
    await overlayPage.evaluate(() => {
      // @ts-ignore
      const partialChecks = [
        { name: "interview_deepfake_video", status: "pass", reason: "Natural visual motion", confidence: 0.88 },
        { name: "interview_voice_auth", status: "unavailable", reason: "Detectif API key not configured in environment", confidence: 0.0 },
        { name: "interview_voice_id", status: "uncertain", reason: "Interviewer voice baseline not enrolled yet", confidence: 0.5 },
        { name: "interview_face_id", status: "pass", reason: "Face embedding matches enrolled candidate", confidence: 0.93 },
        { name: "interview_second_person", status: "pass", reason: "Single face present", confidence: 0.97 },
        { name: "interview_lip_sync", status: "pass", reason: "Phoneme-viseme speech synchronised", confidence: 0.89 },
        { name: "interview_loop", status: "pass", reason: "Continuous physical camera feed", confidence: 0.94 },
      ];
      // @ts-ignore
      if (typeof renderResults === "function") {
        // @ts-ignore
        renderResults({ checks: partialChecks }, "idle", "Partial coverage: voice checks unavailable or pending enrolment. Human review required.");
      }
    });
    await overlayPage.waitForTimeout(400);
    const unavailableOut = path.join(OUT_DIR, "overlay_unavailable.png");
    await overlayPage.screenshot({ path: unavailableOut });
    console.log(`[Capture] Saved: ${unavailableOut}`);

    await overlayContext.close();
    console.log(`[Capture] All UI screenshots successfully refreshed.`);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("[Capture Error]", err);
  process.exit(1);
});
