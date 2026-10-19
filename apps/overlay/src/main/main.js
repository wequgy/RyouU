const {
  app,
  BrowserWindow,
  ipcMain,
  screen,
  desktopCapturer,
  session,
  safeStorage
} = require("electron");
const path = require("path");
const fs = require("fs");
const { exec } = require("child_process");

let mainWindow = null;
let regionSelectorWindow = null;
let detectionTimer = null;
let detectedMeetingApp = "None";
let selectedRegion = null;
let isCompact = false;

// Default server config
const DEFAULT_SERVER_URL = process.env.KYC_BACKEND_URL || "http://127.0.0.1:8000";
let activeSession = null; // { id, token, backendUrl, candidateId }

function log(message, data) {
  console.log(`[RyouU ${new Date().toLocaleTimeString()}] ${message}`, data ?? "");
}

// ----------------- Cross-Platform Meeting App Detection -----------------
function checkMeetingApps() {
  const platform = process.platform;
  let cmd = "";

  if (platform === "win32") {
    cmd = 'tasklist /FO CSV /NH';
  } else if (platform === "darwin") {
    cmd = 'ps -ax -o comm';
  } else {
    cmd = 'ps -e -o comm';
  }

  exec(cmd, { windowsHide: true }, (error, stdout) => {
    if (error) {
      log("Meeting app process check failed", error.message);
      return;
    }

    const lower = stdout.toLowerCase();
    let currentApp = "Manual Tile Selection";

    if (lower.includes("zoom")) {
      currentApp = "Zoom";
    } else if (lower.includes("teams") || lower.includes("ms-teams")) {
      currentApp = "Microsoft Teams";
    } else if (lower.includes("webex")) {
      currentApp = "Cisco Webex";
    } else if (lower.includes("chrome") || lower.includes("firefox") || lower.includes("msedge") || lower.includes("brave")) {
      currentApp = "Browser Meeting (Meet/Teams)";
    }

    if (currentApp !== detectedMeetingApp) {
      detectedMeetingApp = currentApp;
      log(`Meeting app detected: ${detectedMeetingApp}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("detection:app-status", { app: detectedMeetingApp });
      }
    }
  });
}

function startMeetingDetection() {
  if (detectionTimer) return;
  checkMeetingApps();
  detectionTimer = setInterval(checkMeetingApps, 4000);
}

function stopMeetingDetection() {
  if (detectionTimer) {
    clearInterval(detectionTimer);
    detectionTimer = null;
  }
}

// ----------------- Window Management -----------------
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 520,
    height: 800,
    minWidth: 360,
    minHeight: 52,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.setVisibleOnAllWorkspaces(true);

  mainWindow.webContents.on("console-message", (_event, level, message) => {
    log(`RENDERER [${level}]: ${message}`);
  });

  mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function openRegionSelector() {
  if (regionSelectorWindow && !regionSelectorWindow.isDestroyed()) {
    regionSelectorWindow.focus();
    return;
  }

  const display = screen.getPrimaryDisplay();
  const bounds = display.bounds;

  regionSelectorWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    resizable: false,
    movable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  regionSelectorWindow.setAlwaysOnTop(true, "screen-saver");
  regionSelectorWindow.setVisibleOnAllWorkspaces(true);
  regionSelectorWindow.loadFile(path.join(__dirname, "../renderer/picker.html"));

  regionSelectorWindow.on("closed", () => {
    regionSelectorWindow = null;
  });
}

// ----------------- IPC Handlers -----------------
ipcMain.handle("window:close", async () => {
  app.quit();
  return { success: true };
});

ipcMain.handle("window:toggle-compact", async (_event, compact) => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  isCompact = Boolean(compact);
  if (isCompact) {
    mainWindow.setResizable(true);
    mainWindow.setSize(340, 52);
    mainWindow.setResizable(false);
  } else {
    mainWindow.setResizable(true);
    mainWindow.setSize(500, 760);
  }
  return { isCompact };
});

ipcMain.handle("detection:detect-app", async () => {
  checkMeetingApps();
  return { app: detectedMeetingApp };
});

ipcMain.handle("capture:open-picker", async () => {
  openRegionSelector();
  return { success: true };
});

ipcMain.handle("capture:select-region", async (_event, rect) => {
  if (!rect || typeof rect !== "object") {
    return { success: false, error: "Invalid selection." };
  }

  const x = Number(rect.x);
  const y = Number(rect.y);
  const width = Number(rect.width);
  const height = Number(rect.height);

  if (![x, y, width, height].every(Number.isFinite) || width < 40 || height < 40) {
    return { success: false, error: "Selection is too small or invalid." };
  }

  const display = screen.getPrimaryDisplay();
  const left = Math.max(0, Math.min(x, display.size.width));
  const top = Math.max(0, Math.min(y, display.size.height));
  const right = Math.max(left, Math.min(x + width, display.size.width));
  const bottom = Math.max(top, Math.min(y + height, display.size.height));

  selectedRegion = {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
    displayId: String(display.id),
    scaleFactor: display.scaleFactor
  };

  if (regionSelectorWindow && !regionSelectorWindow.isDestroyed()) {
    regionSelectorWindow.close();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.webContents.send("capture:region-selected", selectedRegion);
  }

  return { success: true, region: selectedRegion };
});

ipcMain.handle("capture:cancel-region", async () => {
  if (regionSelectorWindow && !regionSelectorWindow.isDestroyed()) {
    regionSelectorWindow.close();
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
  }
  return { success: true };
});

ipcMain.handle("recording:get-source", async () => {
  const display = screen.getPrimaryDisplay();
  if (!selectedRegion) {
    selectedRegion = {
      x: 0,
      y: 0,
      width: Math.min(1280, display.size.width),
      height: Math.min(720, display.size.height),
      displayId: String(display.id),
      scaleFactor: display.scaleFactor
    };
  }

  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: { width: 1, height: 1 }
  });

  const source = sources.find((item) => String(item.display_id) === selectedRegion.displayId) || sources[0];
  if (!source) {
    return { success: false, error: "Display source not found." };
  }

  return { success: true, sourceId: source.id, region: selectedRegion };
});

// ----------------- Server Interview API Client -----------------
function encryptSecret(plaintext) {
  try {
    if (safeStorage.isEncryptionAvailable()) {
      return safeStorage.encryptString(plaintext).toString("base64");
    }
  } catch (e) {
    log("safeStorage unavailable, falling back to base64 encoding", e.message);
  }
  return Buffer.from(plaintext).toString("base64");
}

function decryptSecret(ciphertext) {
  try {
    const buf = Buffer.from(ciphertext, "base64");
    if (safeStorage.isEncryptionAvailable()) {
      return safeStorage.decryptString(buf);
    }
    return buf.toString("utf8");
  } catch (e) {
    return Buffer.from(ciphertext, "base64").toString("utf8");
  }
}

ipcMain.handle("interview:connect", async (_event, options) => {
  const backendUrl = (options.backendUrl || DEFAULT_SERVER_URL).replace(/\/$/, "");
  const candidateId = options.candidateId || "candidate-001";

  try {
    // If tenant API key provided, create session on server
    if (options.tenantApiKey) {
      const res = await fetch(`${backendUrl}/v1/interviews`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${options.tenantApiKey}`
        },
        body: JSON.stringify({
          candidate_id: candidateId,
          metadata: { meeting_app: detectedMeetingApp, client: "ryouu-desktop-overlay" }
        })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Failed to create interview session: ${res.status} ${errText}`);
      }

      const data = await res.json();
      activeSession = {
        id: data.id,
        token: data.token,
        encryptedToken: encryptSecret(data.token),
        backendUrl,
        candidateId: data.candidate_id,
        expiresAt: data.expires_at
      };

      log("Interview session connected via tenant key", { id: data.id });
      return { success: true, session: { id: data.id, candidateId: data.candidate_id, backendUrl } };
    }

    // Connect with pre-issued interview ID and token
    if (options.interviewId && options.token) {
      activeSession = {
        id: options.interviewId,
        token: options.token,
        encryptedToken: encryptSecret(options.token),
        backendUrl,
        candidateId
      };

      // Verify connection by fetching summary
      const verifyRes = await fetch(`${backendUrl}/v1/interviews/${options.interviewId}/summary`, {
        headers: { "X-Interview-Token": options.token }
      });

      if (!verifyRes.ok) {
        throw new Error(`Interview token invalid or session expired: ${verifyRes.status}`);
      }

      const summary = await verifyRes.json();
      return { success: true, session: { id: options.interviewId, candidateId: summary.candidate_id, backendUrl } };
    }

    throw new Error("Either tenantApiKey or (interviewId + token) must be provided");
  } catch (error) {
    log("Connection error:", error.message);
    return { success: false, error: error.message };
  }
});

ipcMain.handle("interview:upload-clip", async (_event, payload) => {
  if (!activeSession) {
    return { success: false, error: "No active interview session connected." };
  }

  const { round, videoBytes, audioBytes, metadata } = payload;
  const token = decryptSecret(activeSession.encryptedToken);

  try {
    const formData = new FormData();
    const videoBlob = new Blob([videoBytes], { type: "video/webm" });
    formData.append("video", videoBlob, `round_${round}_video.webm`);

    if (audioBytes && audioBytes.byteLength > 0) {
      const audioBlob = new Blob([audioBytes], { type: "audio/wav" });
      formData.append("audio", audioBlob, `round_${round}_audio.wav`);
    }

    formData.append("round", String(round || 1));
    formData.append("meeting_app", detectedMeetingApp || "Unknown");
    if (metadata) {
      if (metadata.resolution) formData.append("resolution", metadata.resolution);
      if (metadata.fps) formData.append("fps", String(metadata.fps));
      if (metadata.timestamp) formData.append("timestamp", String(metadata.timestamp));
    }

    const url = `${activeSession.backendUrl}/v1/interviews/${activeSession.id}/clips`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-Interview-Token": token
      },
      body: formData
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Server returned error ${res.status}: ${errText}`);
    }

    const result = await res.json();
    log("Clip verified successfully by server", {
      round: result.round,
      recommendation: result.overall_recommendation,
      checks: result.checks?.length
    });

    return { success: true, clip: result };
  } catch (error) {
    log("Error uploading clip to backend:", error.message);
    return { success: false, error: error.message };
  }
});

ipcMain.handle("interview:get-summary", async () => {
  if (!activeSession) {
    return { success: false, error: "No active interview session." };
  }
  const token = decryptSecret(activeSession.encryptedToken);

  try {
    const url = `${activeSession.backendUrl}/v1/interviews/${activeSession.id}/summary`;
    const res = await fetch(url, {
      headers: { "X-Interview-Token": token }
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch summary: ${res.status}`);
    }

    const summary = await res.json();
    return { success: true, summary };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle("interview:end", async () => {
  if (!activeSession) return { success: true };
  const token = decryptSecret(activeSession.encryptedToken);

  try {
    const url = `${activeSession.backendUrl}/v1/interviews/${activeSession.id}/end`;
    await fetch(url, {
      method: "POST",
      headers: { "X-Interview-Token": token }
    });
  } catch (e) {
    log("End session notice error:", e.message);
  }
  activeSession = null;
  return { success: true };
});

// ----------------- App Lifecycle -----------------
app.whenReady().then(() => {
  log("RyouU Overlay initialized (Secure Client Architecture)");

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(true);
  });
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    return true;
  });

  session.defaultSession.setDisplayMediaRequestHandler(async (_request, callback) => {
    try {
      const sources = await desktopCapturer.getSources({ types: ["screen"] });
      callback({ video: sources[0], audio: "loopback" });
    } catch (err) {
      log("System audio loopback error:", err.message);
      callback({});
    }
  });

  createMainWindow();
  startMeetingDetection();
});

app.on("before-quit", () => {
  stopMeetingDetection();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
