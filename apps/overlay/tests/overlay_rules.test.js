const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const { computeEffectiveRecommendation } = require("../src/renderer/renderer.js");

test("Security: No tenant API key ever appears under apps/overlay", () => {
  const overlayRoot = path.resolve(__dirname, "..");
  const forbiddenPatterns = [
    ["kyc", "demo", "lenient", "key"].join("_"),
    ["kyc", "demo", "strict", "key"].join("_"),
    ["tenant", "Api", "Key"].join(""),
    ["kyc", "live", ""].join("_"),
  ];

  function scanDir(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "node_modules" && entry.name !== "dist" && entry.name !== ".git" && entry.name !== "tests") {
          scanDir(fullPath);
        }
      } else if (entry.isFile() && (entry.name.endsWith(".js") || entry.name.endsWith(".html") || entry.name.endsWith(".json"))) {
        const content = fs.readFileSync(fullPath, "utf8");
        for (const forbidden of forbiddenPatterns) {
          assert.strictEqual(
            content.includes(forbidden),
            false,
            `Forbidden pattern '${forbidden}' found in ${fullPath}`
          );
        }
      }
    }
  }

  scanDir(overlayRoot);
});

test("Banner rule: Banner is NEVER green when any check is idle, unavailable, or not enrolled", () => {
  // Case 1: 6 checks clear, but voice is 'not enrolled' -> MUST NOT BE CLEAR (green)
  const checksWithUnenrolled = [
    { name: "interview_deepfake_video", status: "pass", reason: "Natural visual motion" },
    { name: "interview_face_drift", status: "pass", reason: "Face matches enrolled candidate" },
    { name: "interview_multiple_faces", status: "pass", reason: "Single face present" },
    { name: "interview_voice_clone", status: "pass", reason: "Natural acoustic timbre" },
    { name: "interview_speaker_match", status: "uncertain", reason: "Interviewer voice not enrolled yet" },
    { name: "interview_audio_visual_sync", status: "pass", reason: "Lip-sync synchronized" },
    { name: "interview_virtual_camera", status: "pass", reason: "Hardware camera driver" }
  ];
  const rec1 = computeEffectiveRecommendation("clear", checksWithUnenrolled);
  assert.notStrictEqual(rec1, "clear", "Banner must not be clear/green when speaker match is not enrolled");
  assert.strictEqual(rec1, "idle");

  // Case 2: One check is 'idle' -> MUST NOT BE CLEAR
  const checksWithIdle = [
    { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
    { name: "interview_audio_visual_sync", status: "idle", reason: "Waiting for spoken speech" }
  ];
  const rec2 = computeEffectiveRecommendation("clear", checksWithIdle);
  assert.notStrictEqual(rec2, "clear", "Banner must not be clear/green when a check is idle");
  assert.strictEqual(rec2, "idle");

  // Case 3: One check is 'unavailable' -> MUST NOT BE CLEAR
  const checksWithUnavailable = [
    { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
    { name: "interview_voice_clone", status: "unavailable", reason: "Detectif API not configured" }
  ];
  const rec3 = computeEffectiveRecommendation("clear", checksWithUnavailable);
  assert.notStrictEqual(rec3, "clear", "Banner must not be clear/green when a check is unavailable");
  assert.strictEqual(rec3, "idle");

  // Case 4: No checks yet (empty) -> MUST NOT BE CLEAR
  const rec4 = computeEffectiveRecommendation("clear", []);
  assert.notStrictEqual(rec4, "clear", "Banner must not be clear/green with empty checks");
  assert.strictEqual(rec4, "idle");

  // Case 5: When all active checks pass -> CAN be clear (green)
  const allClear = [
    { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
    { name: "interview_face_drift", status: "pass", reason: "Face matches baseline" },
    { name: "interview_multiple_faces", status: "pass", reason: "Single face" },
    { name: "interview_voice_clone", status: "pass", reason: "Natural acoustic timbre" },
    { name: "interview_speaker_match", status: "pass", reason: "Voice matches speaker baseline" },
    { name: "interview_audio_visual_sync", status: "pass", reason: "Lips synchronized" },
    { name: "interview_virtual_camera", status: "pass", reason: "Physical camera driver" }
  ];
  const rec5 = computeEffectiveRecommendation("clear", allClear);
  assert.strictEqual(rec5, "clear");

  // Case 6: Anomaly detected -> MUST be flagged
  const flagged = [
    ...allClear.slice(0, 6),
    { name: "interview_virtual_camera", status: "flagged", reason: "OBS Virtual Camera software driver detected" }
  ];
  const rec6 = computeEffectiveRecommendation("clear", flagged);
  assert.strictEqual(rec6, "flagged");
});

test("Default View: Styles enforce overflow hidden (no scrollbar in default view)", () => {
  const cssPath = path.resolve(__dirname, "../src/renderer/styles.css");
  const css = fs.readFileSync(cssPath, "utf8");
  
  assert.match(css, /body\s*\{[^}]*overflow:\s*hidden/);
  assert.match(css, /\.app-container\s*\{[^}]*overflow:\s*hidden/);
});
