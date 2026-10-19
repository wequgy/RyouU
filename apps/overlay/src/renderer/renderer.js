/**
 * RyouU Real-time Interview Integrity Monitoring Renderer
 * Displays verified signals from the 7 backend checks only.
 */

// DOM Elements helper
const getEl = (id) => (typeof document !== "undefined" ? document.getElementById(id) : null);

const fullPanel = getEl("fullPanel");
const compactPill = getEl("compactPill");
const compactStatusBadge = getEl("compactStatusBadge");
const compactStatusText = getEl("compactStatusText");
const compactAppText = getEl("compactAppText");
const compactExpandBtn = getEl("compactExpandBtn");
const minimizeBtn = getEl("minimizeBtn");
const closeBtn = getEl("closeBtn");

const meetingAppName = getEl("meetingAppName");
const selectRegionBtn = getEl("selectRegionBtn");
const regionBtnText = getEl("regionBtnText");
const recordOnceBtn = getEl("recordOnceBtn");
const recordBtnText = getEl("recordBtnText");
const autoMonitorBtn = getEl("autoMonitorBtn");
const autoMonitorIcon = getEl("autoMonitorIcon");
const autoMonitorBtnText = getEl("autoMonitorBtnText");
const exportReportBtn = getEl("exportReportBtn");

const cropCanvas = getEl("cropCanvas");
const cropCtx = cropCanvas && cropCanvas.getContext ? cropCanvas.getContext("2d", { willReadFrequently: true }) : null;
const captureVideo = getEl("captureVideo");
const videoPlaceholder = getEl("videoPlaceholder");
const signalDetectedTooltip = getEl("signalDetectedTooltip");
const signalTooltipText = getEl("signalTooltipText");

const timelineProgress = getEl("timelineProgress");
const timelineTimestamp = getEl("timelineTimestamp");
const timelineAlertMarker = getEl("timelineAlertMarker");
const timelinePlayBtn = getEl("timelinePlayBtn");

const sessionOverallPill = getEl("sessionOverallPill");
const capsuleAuthVal = getEl("capsuleAuthVal");
const capsuleNetVal = getEl("capsuleNetVal");
const recBanner = getEl("recommendationBanner");
const recIcon = getEl("recIcon");
const recActionText = getEl("recActionText");
const timelineChips = getEl("timelineChips");
const roundsCountLabel = getEl("roundsCountLabel");

// State
let isAutoMonitoring = false;
let isRecording = false;
let activeRecorder = null;
let recordingTimeoutId = null;
let currentRound = 1;
let currentRegion = null;
let captureStream = null;
let animFrameId = null;
let autoIntervalTimer = null;
let recordingTimer = null;
let sessionHistory = [];
let recordingElapsedMs = 0;

const RECORDING_DURATION_MS = 25000; // 25s maximum per chunk
const AUTO_MONITOR_INTERVAL_MS = 60000; // 60s

// ----------------- Accordion Interactions -----------------
function setupAccordions() {
  document.querySelectorAll(".signal-item-main").forEach((header) => {
    header.addEventListener("click", () => {
      const card = header.closest(".signal-item-card");
      const toggleKey = header.getAttribute("data-toggle");
      const drawer = document.getElementById(`drawer-${toggleKey}`);
      if (!card || !drawer) return;

      const isOpen = card.classList.contains("open");
      if (isOpen) {
        card.classList.remove("open");
        drawer.classList.add("hidden");
      } else {
        card.classList.add("open");
        drawer.classList.remove("hidden");
      }
    });
  });

  // Interactive timeline alert marker click: scroll to flagged card
  if (timelineAlertMarker) {
    timelineAlertMarker.addEventListener("click", (e) => {
      e.stopPropagation();
      const flaggedCard = document.querySelector(".signal-item-card.open") || document.getElementById("item-deepfake_video");
      if (flaggedCard) {
        flaggedCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }
}

// ----------------- Initialization & Connections -----------------
async function initSession() {
  setupAccordions();

  // Initial meeting app detection
  const appInfo = await window.ryouu.detectMeetingApp();
  if (appInfo && appInfo.app) {
    updateMeetingApp(appInfo.app);
  }

  // Attempt connection with automatic retry if backend is starting
  attemptConnect();
}

async function attemptConnect() {
  try {
    const launchSession = await window.ryouu.getLaunchSession();
    const urlParams = new URLSearchParams(window.location.search);
    const paramId = urlParams.get("interview_id") || urlParams.get("id");
    const paramToken = urlParams.get("token");
    const paramExpires = urlParams.get("expires_at");

    let sessionPayload = launchSession || (paramId && paramToken ? {
      interviewId: paramId,
      token: paramToken,
      expiresAt: paramExpires ? parseInt(paramExpires) : null
    } : null);

    if (!sessionPayload) {
      try {
        const devRes = await fetch("http://127.0.0.1:8000/v1/interviews/dev-session", { method: "POST" });
        if (devRes.ok) {
          const devData = await devRes.json();
          sessionPayload = {
            interviewId: devData.interview_id,
            token: devData.token,
            expiresAt: devData.expires_at
          };
        }
      } catch (_) {}
    }

    if (sessionPayload && sessionPayload.interviewId && sessionPayload.token) {
      const res = await window.ryouu.connectInterview(sessionPayload);
      if (res.success) {
        console.log("[RyouU] Connected to interview engine via scoped interviewer token:", res.session);
        capsuleNetVal.textContent = "Connected";
        capsuleNetVal.className = "capsule-value strong";
        return;
      } else {
        console.warn("[RyouU] Session connection failed:", res.error);
        capsuleNetVal.textContent = "Auth Error";
        capsuleNetVal.className = "capsule-value warn";
        return;
      }
    }

    // No credentials provided yet; overlay waits in ready state
    capsuleNetVal.textContent = "Awaiting Token";
    capsuleNetVal.className = "capsule-value";
  } catch (err) {
    console.log("[RyouU] Waiting for session credentials...", err);
    capsuleNetVal.textContent = "Awaiting Token";
    capsuleNetVal.className = "capsule-value";
  }
}

function updateMeetingApp(app) {
  meetingAppName.textContent = app;
  compactAppText.textContent = app;
}

// ----------------- Compact Pill vs Full Panel -----------------
function setCompactMode(compact) {
  if (compact) {
    fullPanel.classList.add("hidden");
    compactPill.classList.remove("hidden");
    window.ryouu.toggleCompact(true);
  } else {
    compactPill.classList.add("hidden");
    fullPanel.classList.remove("hidden");
    window.ryouu.toggleCompact(false);
  }
}

if (minimizeBtn) minimizeBtn.addEventListener("click", () => setCompactMode(true));
if (compactExpandBtn) compactExpandBtn.addEventListener("click", () => setCompactMode(false));
if (closeBtn) closeBtn.addEventListener("click", () => window?.ryouu?.closeApp?.());

// ----------------- Region Selection & Capture Setup -----------------
if (selectRegionBtn) {
  selectRegionBtn.addEventListener("click", async () => {
    if (regionBtnText) regionBtnText.textContent = "Selecting...";
    await window?.ryouu?.openCapturePicker?.();
  });
}

if (typeof window !== "undefined" && window.ryouu) {
  window.ryouu.onRegionSelected?.((region) => {
    currentRegion = region;
    if (regionBtnText) regionBtnText.textContent = `${Math.round(region.width)}x${Math.round(region.height)}`;
    console.log("[Unclone] Candidate tile selected:", region);
    setupMediaStreams();
  });

  window.ryouu.onMeetingAppDetected?.((data) => {
    if (data && data.app) {
      updateMeetingApp(data.app);
    }
  });
}

async function setupMediaStreams() {
  try {
    const sourceRes = await window.ryouu.getRecordingSource();
    if (!sourceRes.success) {
      console.warn("[RyouU] Recording source notice:", sourceRes.error);
      return false;
    }

    if (!currentRegion && sourceRes.region) {
      currentRegion = sourceRes.region;
    }

    if (!currentRegion) {
      currentRegion = { x: 0, y: 0, width: 1280, height: 720 };
    }

    if (captureStream) {
      captureStream.getTracks().forEach((t) => t.stop());
    }

    // Request desktop video + system audio loopback from meeting app
    try {
      captureStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: "desktop"
          }
        },
        video: {
          mandatory: {
            chromeMediaSource: "desktop",
            chromeMediaSourceId: sourceRes.sourceId,
            minWidth: 1280,
            maxWidth: 3840,
            minHeight: 720,
            maxHeight: 2160,
            minFrameRate: 30,
            maxFrameRate: 30
          }
        }
      });
      console.log("[RyouU] Desktop stream captured with system audio loopback:", captureStream.getAudioTracks().length);
    } catch (audioErr) {
      console.warn("[RyouU] Desktop loopback audio request fallback:", audioErr.message);
      captureStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          mandatory: {
            chromeMediaSource: "desktop",
            chromeMediaSourceId: sourceRes.sourceId,
            minWidth: 1280,
            maxWidth: 3840,
            minHeight: 720,
            maxHeight: 2160,
            minFrameRate: 30,
            maxFrameRate: 30
          }
        }
      });
    }

    captureVideo.srcObject = captureStream;
    await captureVideo.play();

    // Hide placeholder and show active canvas
    videoPlaceholder.style.display = "none";
    cropCanvas.style.display = "block";
    cropCanvas.width = currentRegion.width || 1280;
    cropCanvas.height = currentRegion.height || 720;

    if (animFrameId) cancelAnimationFrame(animFrameId);
    renderCropLoop();

    return true;
  } catch (err) {
    console.error("[RyouU] Capture setup error:", err);
    return false;
  }
}

function renderCropLoop() {
  if (captureVideo && captureVideo.readyState >= 2 && currentRegion) {
    cropCtx.drawImage(
      captureVideo,
      currentRegion.x || 0,
      currentRegion.y || 0,
      currentRegion.width || cropCanvas.width,
      currentRegion.height || cropCanvas.height,
      0,
      0,
      cropCanvas.width,
      cropCanvas.height
    );
  }
  animFrameId = requestAnimationFrame(renderCropLoop);
}

// ----------------- Recording & Upload Pipeline -----------------
async function recordAndAnalyzeClip() {
  // If already recording, clicking the button triggers EARLY STOP & IMMEDIATE ANALYSIS
  if (isRecording) {
    if (activeRecorder && activeRecorder.state === "recording") {
      console.log("[RyouU] User clicked Stop & Analyze early. Finalizing clip...");
      if (recordBtnText) recordBtnText.textContent = "Stopping...";
      activeRecorder.stop();
    }
    return;
  }

  isRecording = true;
  recordOnceBtn.classList.add("recording");
  if (recordBtnText) recordBtnText.textContent = "Connecting...";

  const ready = await setupMediaStreams();
  if (!ready) {
    isRecording = false;
    recordOnceBtn.classList.remove("recording");
    if (recordBtnText) recordBtnText.textContent = "Record 25s";
    return;
  }

  // Active recording button state
  if (recordBtnText) recordBtnText.textContent = "Stop (00:00)";

  // Start timeline animation
  recordingElapsedMs = 0;
  timelineAlertMarker.classList.add("hidden");
  signalDetectedTooltip.classList.add("hidden");

  if (recordingTimer) clearInterval(recordingTimer);
  recordingTimer = setInterval(() => {
    recordingElapsedMs += 250;
    const progress = Math.min(100, (recordingElapsedMs / RECORDING_DURATION_MS) * 100);
    timelineProgress.style.width = `${progress}%`;

    const sec = Math.floor(recordingElapsedMs / 1000);
    const secStr = sec < 10 ? `0${sec}` : `${sec}`;
    timelineTimestamp.textContent = `00:${secStr} / 00:25`;
    if (recordBtnText && isRecording && activeRecorder && activeRecorder.state === "recording") {
      recordBtnText.textContent = `Stop (00:${secStr})`;
    }
  }, 250);

  let audioRecorder = null;
  const audioChunks = [];

  try {
    const canvasStream = cropCanvas.captureStream(30);

    // Attach system audio loopback from the meeting screen capture stream (NOT microphone!)
    if (captureStream) {
      const loopbackTracks = captureStream.getAudioTracks();
      if (loopbackTracks.length > 0) {
        canvasStream.addTrack(loopbackTracks[0]);
        console.log("[RyouU] Candidate meeting loopback audio attached to clip:", loopbackTracks[0].label);

        try {
          const audioMime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm";
          audioRecorder = new MediaRecorder(new MediaStream(loopbackTracks), { mimeType: audioMime });
          audioRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) audioChunks.push(e.data);
          };
          audioRecorder.start(1000);
        } catch (e) {
          console.warn("[RyouU] Loopback audio recorder setup:", e.message);
        }
      } else {
        // Fallback to getDisplayMedia loopback if captureStream did not include audio
        try {
          const displayStream = await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: true
          });
          const aTracks = displayStream.getAudioTracks();
          if (aTracks.length > 0) {
            canvasStream.addTrack(aTracks[0]);
            console.log("[RyouU] System audio loopback linked from display handler");

            const audioMime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
              ? "audio/webm;codecs=opus"
              : "audio/webm";
            audioRecorder = new MediaRecorder(new MediaStream(aTracks), { mimeType: audioMime });
            audioRecorder.ondataavailable = (e) => {
              if (e.data && e.data.size > 0) audioChunks.push(e.data);
            };
            audioRecorder.start(1000);
          }
          displayStream.getVideoTracks().forEach(t => t.stop());
        } catch (err) {
          console.warn("[RyouU] DisplayMedia loopback notice:", err.message);
        }
      }
    }

    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")
      ? "video/webm;codecs=vp8,opus"
      : "video/webm";

    const recorder = new MediaRecorder(canvasStream, { mimeType });
    activeRecorder = recorder;
    const chunks = [];

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };

    const stopPromise = new Promise((resolve) => {
      recorder.onstop = resolve;
    });

    recorder.start(1000);

    // Auto-stop at 25 seconds unless user clicked "Stop" early
    recordingTimeoutId = setTimeout(() => {
      if (recorder.state === "recording") {
        recorder.stop();
      }
    }, RECORDING_DURATION_MS);

    // Wait until stopped (either by timer or early user click)
    await stopPromise;

    if (audioRecorder && audioRecorder.state === "recording") {
      audioRecorder.stop();
      await new Promise((resolve) => (audioRecorder.onstop = resolve));
    }

    if (recordingTimeoutId) clearTimeout(recordingTimeoutId);
    if (recordingTimer) clearInterval(recordingTimer);

    const elapsedSec = Math.max(1, Math.floor(recordingElapsedMs / 1000));
    const secStr = elapsedSec < 10 ? `0${elapsedSec}` : `${elapsedSec}`;
    timelineTimestamp.textContent = `00:${secStr} / 00:25`;

    recordOnceBtn.classList.remove("recording");
    recordOnceBtn.classList.add("analyzing");
    if (recordBtnText) recordBtnText.textContent = "Analyzing...";

    const videoBlob = new Blob(chunks, { type: "video/webm" });
    const videoBytes = await videoBlob.arrayBuffer();

    let audioBytes = new ArrayBuffer(0);
    if (audioChunks.length > 0) {
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      audioBytes = await audioBlob.arrayBuffer();
    }

    console.log(`[RyouU] Uploading clip: video=${videoBytes.byteLength}B, audio=${audioBytes.byteLength}B (${elapsedSec}s)`);

    // Upload to FastAPI server
    const uploadRes = await window.ryouu.uploadClip({
      round: currentRound,
      videoBytes,
      audioBytes,
      metadata: {
        resolution: `${currentRegion.width}x${currentRegion.height}`,
        fps: 30,
        timestamp: Date.now() / 1000,
        duration: elapsedSec
      }
    });

    if (uploadRes.success && uploadRes.clip) {
      applyClipResults(uploadRes.clip);
      currentRound += 1;
    } else {
      console.warn("[RyouU] Clip upload notice:", uploadRes.error);
      if (recActionText) recActionText.textContent = uploadRes.error || "Analysis error";
      if (capsuleNetVal) {
        capsuleNetVal.textContent = "Upload Error";
        capsuleNetVal.className = "capsule-value warn";
      }
    }
  } catch (err) {
    console.error("Recording error:", err);
  } finally {
    isRecording = false;
    activeRecorder = null;
    recordOnceBtn.classList.remove("recording", "analyzing");
    if (recordBtnText) recordBtnText.textContent = "Record 25s";
  }
}

function computeEffectiveRecommendation(rawRec, checks) {
  const checkList = Array.isArray(checks) ? checks : [];
  if (checkList.length === 0) return "idle";

  const hasFlagged = checkList.some((c) => {
    const s = (c.status || "").toLowerCase();
    return s === "flagged" || s === "fail";
  });
  if (hasFlagged) return "flagged";

  const hasCaution = checkList.some((c) => {
    const s = (c.status || "").toLowerCase();
    return s === "caution" || s === "review_recommended";
  });
  if (hasCaution) return "caution";

  const anyIncompleteOrNotEnrolled = checkList.some((c) => {
    const s = (c.status || "").toLowerCase();
    const r = (c.reason || "").toLowerCase();
    return (
      s === "idle" ||
      s === "unavailable" ||
      s === "uncertain" ||
      r.includes("not enrolled") ||
      r.includes("no kyc baseline") ||
      r.includes("unavailable") ||
      r.includes("idle")
    );
  });

  // Strict Rule: Banner is NEVER green when any check is idle, unavailable, uncertain, or not enrolled
  if (anyIncompleteOrNotEnrolled) {
    return "idle";
  }

  return rawRec === "clear" ? "clear" : "idle";
}

// ----------------- UI Signal Presentation -----------------
function applyClipResults(clip) {
  sessionHistory.push(clip);

  const checks = Array.isArray(clip.checks) ? clip.checks : [];
  const rec = computeEffectiveRecommendation(clip.overall_recommendation, checks);
  const action = clip.interviewer_action || (
    rec === "clear"
      ? "All biometric and acoustic signals consistent. Continue interview normally."
      : "Some integrity checks are idle, uncalibrated or not enrolled. Ongoing monitoring active."
  );

  // 1. Update Callout Guidance Banner (Never green when idle/unavailable/not enrolled)
  recBanner.className = `recommendation-callout ${rec}`;
  recActionText.textContent = action;

  // 2. Update Verdict Header & Authenticity Capsule
  if (rec === "flagged") {
    recIcon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
    sessionOverallPill.className = "session-status-pill flagged";
    sessionOverallPill.textContent = "SIGNAL DETECTED";
    capsuleAuthVal.textContent = "High Risk";
    capsuleAuthVal.className = "capsule-value flagged";

    compactStatusBadge.className = "pill-status-capsule flagged";
    compactStatusText.textContent = "SIGNAL DETECTED";

    // Show floating alert pin on timeline
    timelineAlertMarker.classList.remove("hidden");
    signalDetectedTooltip.classList.remove("hidden");
    signalTooltipText.textContent = "Signal Anomaly Detected";
  } else if (rec === "caution") {
    recIcon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    sessionOverallPill.className = "session-status-pill caution";
    sessionOverallPill.textContent = "CAUTION / REVIEW";
    capsuleAuthVal.textContent = "Review Needed";
    capsuleAuthVal.className = "capsule-value moderate";

    compactStatusBadge.className = "pill-status-capsule caution";
    compactStatusText.textContent = "CAUTION / REVIEW";

    timelineAlertMarker.classList.remove("hidden");
    signalDetectedTooltip.classList.remove("hidden");
    signalTooltipText.textContent = "Review Recommended";
  } else if (rec === "clear") {
    recIcon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    sessionOverallPill.className = "session-status-pill clear";
    sessionOverallPill.textContent = "ALL CLEAR";
    capsuleAuthVal.textContent = "Verified Strong";
    capsuleAuthVal.className = "capsule-value strong";

    compactStatusBadge.className = "pill-status-capsule";
    compactStatusText.textContent = "ALL SIGNALS CLEAR";

    timelineAlertMarker.classList.add("hidden");
    signalDetectedTooltip.classList.add("hidden");
  } else {
    // rec === "idle" / uncalibrated / incomplete coverage: Never green!
    recIcon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
    sessionOverallPill.className = "session-status-pill idle";
    sessionOverallPill.textContent = "MONITORING ACTIVE";
    capsuleAuthVal.textContent = "Partial Coverage";
    capsuleAuthVal.className = "capsule-value";

    compactStatusBadge.className = "pill-status-capsule";
    compactStatusText.textContent = "MONITORING ACTIVE";

    timelineAlertMarker.classList.add("hidden");
    signalDetectedTooltip.classList.add("hidden");
  }

  // 3. Update the 7 Real Signal Cards
  if (Array.isArray(clip.checks)) {
    for (const chk of clip.checks) {
      updateSignalItem(chk);
    }
  }

  // 4. Add Round to Timeline
  appendRoundChip(clip);
}

function updateSignalItem(chk) {
  const key = chk.name.replace("interview_", "");
  const cardEl = document.getElementById(`item-${key}`);
  const countEl = document.getElementById(`count-${key}`);
  const barsEl = document.getElementById(`bars-${key}`);
  const drawerEl = document.getElementById(`drawer-${key}`);
  const detailEl = document.getElementById(`detail-${key}`);
  const dotEl = document.getElementById(`dot-${key}`);

  if (!countEl || !barsEl || !detailEl) return;

  const status = chk.status;
  const isFail = status === "fail";
  const isCaution = status === "uncertain";

  // Update reason in accordion drawer
  const confText = chk.confidence !== undefined ? ` (Confidence: ${Math.round(chk.confidence * 100)}%)` : "";
  detailEl.innerHTML = `<strong>${chk.reason || "Integrity verification verified."}</strong>${confText}`;

  // Update Count Badge & Bullet Dot
  if (isFail) {
    countEl.textContent = "1";
    countEl.className = "signal-count-badge has-flags";
    if (dotEl) dotEl.className = "bullet-dot red";

    // Auto-expand flagged card so interviewer immediately sees why!
    if (cardEl && drawerEl) {
      cardEl.classList.add("open");
      drawerEl.classList.remove("hidden");
    }
  } else if (isCaution) {
    countEl.textContent = "1";
    countEl.className = "signal-count-badge has-caution";
    if (dotEl) dotEl.className = "bullet-dot amber";

    // Auto-expand caution card
    if (cardEl && drawerEl) {
      cardEl.classList.add("open");
      drawerEl.classList.remove("hidden");
    }
  } else {
    countEl.textContent = "0";
    countEl.className = "signal-count-badge is-clear";
    if (dotEl) dotEl.className = "bullet-dot green";
  }

  // Update 4-bar Signal Indicator
  barsEl.className = "signal-bars";
  const bars = barsEl.querySelectorAll(".bar");
  if (bars.length >= 4) {
    if (isFail) {
      barsEl.classList.add("flagged");
      bars[0].className = "bar bar-1 active";
      bars[1].className = "bar bar-2 active";
      bars[2].className = "bar bar-3 active";
      bars[3].className = "bar bar-4 active";
    } else if (isCaution) {
      barsEl.classList.add("caution");
      bars[0].className = "bar bar-1 active";
      bars[1].className = "bar bar-2 active";
      bars[2].className = "bar bar-3";
      bars[3].className = "bar bar-4";
    } else {
      barsEl.classList.add("clear");
      bars[0].className = "bar bar-1 active";
      bars[1].className = "bar bar-2";
      bars[2].className = "bar bar-3";
      bars[3].className = "bar bar-4";
    }
  }
}

function appendRoundChip(clip) {
  const roundNum = clip.round || sessionHistory.length;
  const rec = clip.overall_recommendation || "clear";
  const svgIcon = rec === "flagged"
    ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path></svg>'
    : rec === "caution"
    ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
    : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8"><polyline points="20 6 9 17 4 12"></polyline></svg>';

  const chip = document.createElement("div");
  chip.className = "round-chip active";
  chip.innerHTML = `<span>Round ${roundNum}</span> <span class="round-chip-icon">${svgIcon}</span>`;

  chip.addEventListener("click", () => {
    document.querySelectorAll(".round-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    if (clip.checks) clip.checks.forEach(updateSignalItem);
    recActionText.textContent = clip.interviewer_action;
    recBanner.className = `recommendation-callout ${clip.overall_recommendation || "clear"}`;
  });

  if (timelineChips.querySelector(".empty-timeline-msg")) {
    timelineChips.innerHTML = "";
  }

  timelineChips.appendChild(chip);
  roundsCountLabel.textContent = `${sessionHistory.length} Round${sessionHistory.length > 1 ? "s" : ""} Completed`;
}

// ----------------- Controls -----------------
if (autoMonitorBtn) {
  autoMonitorBtn.addEventListener("click", () => {
    if (isAutoMonitoring) {
      isAutoMonitoring = false;
      if (autoIntervalTimer) clearInterval(autoIntervalTimer);
      autoMonitorBtn.classList.remove("active");
      if (autoMonitorIcon) autoMonitorIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
      if (autoMonitorBtnText) autoMonitorBtnText.textContent = "Auto-Monitor";
    } else {
      isAutoMonitoring = true;
      autoMonitorBtn.classList.add("active");
      if (autoMonitorIcon) autoMonitorIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
      if (autoMonitorBtnText) autoMonitorBtnText.textContent = "Pause Auto";
      recordAndAnalyzeClip();
      autoIntervalTimer = setInterval(() => {
        if (isAutoMonitoring && !isRecording) {
          recordAndAnalyzeClip();
        }
      }, AUTO_MONITOR_INTERVAL_MS);
    }
  });
}

if (recordOnceBtn) {
  recordOnceBtn.addEventListener("click", () => {
    recordAndAnalyzeClip();
  });
}

if (timelinePlayBtn) {
  timelinePlayBtn.addEventListener("click", () => {
    recordAndAnalyzeClip();
  });
}

// Export Printable Report
if (exportReportBtn) {
  exportReportBtn.addEventListener("click", () => {
  if (sessionHistory.length === 0) {
    alert("No interview rounds recorded yet to export.");
    return;
  }

  const dateStr = new Date().toLocaleString();
  const rows = sessionHistory.map((c) => {
    const list = (c.checks || []).map((k) => `<li><strong>${k.name.replace("interview_", "")}</strong>: <span class="badge ${k.status}">${k.status.toUpperCase()}</span> - ${k.reason}</li>`).join("");
    return `
      <div style="margin-bottom: 24px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h3>Round ${c.round} — <span style="text-transform: uppercase;">${c.overall_recommendation}</span></h3>
        <p><strong>Guidance:</strong> ${c.interviewer_action}</p>
        <ul style="line-height: 1.6; font-size: 13px;">${list}</ul>
      </div>
    `;
  }).join("");

  const reportHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Unclone Integrity Report</title>
      <style>
        body { font-family: -apple-system, sans-serif; padding: 40px; background: #fafafa; color: #1e293b; }
        .card { max-width: 800px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0; }
        .badge.pass { color: #15803d; font-weight: 700; }
        .badge.fail { color: #b91c1c; font-weight: 700; }
        .badge.uncertain { color: #b45309; font-weight: 700; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Unclone Live Interview Integrity Report</h1>
        <p style="color: #64748b; font-size: 14px;">Date: ${dateStr} | Total Rounds: ${sessionHistory.length}</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;"/>
        ${rows}
      </div>
    </body>
    </html>
  `;

  const blob = new Blob([reportHtml], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  });
}

if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", initSession);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    computeEffectiveRecommendation,
  };
}
