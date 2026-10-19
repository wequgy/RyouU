const { contextBridge, ipcRenderer } = require("electron");

console.log("[RyouU] Preload initialized with secure context isolation");

contextBridge.exposeInMainWorld("ryouu", {
  // Session & Server Communication
  connectInterview: (options) => ipcRenderer.invoke("interview:connect", options),
  uploadClip: (payload) => ipcRenderer.invoke("interview:upload-clip", payload),
  getSummary: () => ipcRenderer.invoke("interview:get-summary"),
  endInterview: () => ipcRenderer.invoke("interview:end"),

  // Meeting App & Capture
  detectMeetingApp: () => ipcRenderer.invoke("detection:detect-app"),
  openCapturePicker: () => ipcRenderer.invoke("capture:open-picker"),
  selectCaptureRegion: (rect) => ipcRenderer.invoke("capture:select-region", rect),
  cancelCaptureRegion: () => ipcRenderer.invoke("capture:cancel-region"),
  getRecordingSource: () => ipcRenderer.invoke("recording:get-source"),

  // Window Controls
  toggleCompact: (isCompact) => ipcRenderer.invoke("window:toggle-compact", isCompact),
  closeApp: () => ipcRenderer.invoke("window:close"),

  // Reactive Subscriptions
  onMeetingAppDetected: (callback) => {
    ipcRenderer.on("detection:app-status", (_event, data) => callback(data));
  },
  onRegionSelected: (callback) => {
    ipcRenderer.on("capture:region-selected", (_event, region) => callback(region));
  }
});
