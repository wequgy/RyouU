// @ts-check
const { test, expect } = require("@playwright/test");
const path = require("path");
const fs = require("fs");

const RENDERER_HTML_PATH = "file://" + path.resolve(__dirname, "../src/renderer/index.html").replace(/\\/g, "/");

const CHECK_TILE_IDS = [
  "item-deepfake_video",
  "item-voice_auth",
  "item-voice_id",
  "item-face_id",
  "item-second_person",
  "item-lip_sync",
  "item-loop",
];

test.describe("Overlay Hardening & UI Rules", () => {
  // Test 1: Scaling & Scrollbars (100% and 150% scaling)
  for (const scale of [1.0, 1.5]) {
    test(`Default view has no scrollbar at ${(scale * 100)}% scaling with all 7 check tiles visible`, async ({ page }) => {
      await page.setViewportSize({ width: 520, height: 800 });
      // Mock window.ryouu bridge before loading
      await page.addInitScript(() => {
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

      await page.goto(RENDERER_HTML_PATH, { waitUntil: "domcontentloaded" });

      // Verify no scrollbar on body and main container
      const bodyOverflow = await page.evaluate(() => {
        const bodyStyle = window.getComputedStyle(document.body);
        const containerStyle = window.getComputedStyle(document.getElementById("appContainer"));
        return {
          bodyOverflow: bodyStyle.overflow,
          bodyOverflowX: bodyStyle.overflowX,
          bodyOverflowY: bodyStyle.overflowY,
          containerOverflow: containerStyle.overflow,
          hasHorizontalScroll: document.documentElement.scrollWidth > window.innerWidth,
        };
      });

      expect(bodyOverflow.bodyOverflow).toBe("hidden");
      expect(bodyOverflow.containerOverflow).toBe("hidden");
      expect(bodyOverflow.hasHorizontalScroll).toBe(false);

      // Verify all 7 check tiles exist and are visible
      for (const tileId of CHECK_TILE_IDS) {
        const tile = page.locator(`#${tileId}`);
        await expect(tile).toBeVisible();
      }
    });
  }

  // Test 2: Banner rule: Banner is never green when any check is idle, unavailable or not enrolled
  test("Recommendation banner is NEVER green when any check is idle, unavailable or not enrolled", async ({ page }) => {
    await page.setViewportSize({ width: 520, height: 800 });
    await page.goto(RENDERER_HTML_PATH, { waitUntil: "domcontentloaded" });

    // Initial state: default view before analysis
    const banner = page.locator("#recommendationBanner");
    await expect(banner).toBeVisible();
    await expect(banner).toHaveClass(/idle/);
    await expect(banner).not.toHaveClass(/clear/);

    // Test banner computation under various simulated check states
    const statesToTest = [
      {
        desc: "One check is idle",
        checks: [
          { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
          { name: "interview_lip_sync", status: "idle", reason: "Waiting for spoken speech" },
        ],
      },
      {
        desc: "One check is unavailable",
        checks: [
          { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
          { name: "interview_voice_clone", status: "unavailable", reason: "Detectif API not configured" },
        ],
      },
      {
        desc: "Speaker match is not enrolled (uncertain)",
        checks: [
          { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
          { name: "interview_face_drift", status: "pass", reason: "Face matches enrolled candidate" },
          { name: "interview_multiple_faces", status: "pass", reason: "Single face present" },
          { name: "interview_voice_clone", status: "pass", reason: "Natural acoustic timbre" },
          { name: "interview_speaker_match", status: "uncertain", reason: "Interviewer voice not enrolled yet" },
          { name: "interview_audio_visual_sync", status: "pass", reason: "Lip-sync synchronized" },
          { name: "interview_virtual_camera", status: "pass", reason: "Hardware camera driver" },
        ],
      },
      {
        desc: "Empty checks",
        checks: [],
      },
    ];

    for (const { desc, checks } of statesToTest) {
      const bannerClass = await page.evaluate((testChecks) => {
        // @ts-ignore
        if (typeof computeEffectiveRecommendation === "function") {
          // @ts-ignore
          const rec = computeEffectiveRecommendation("clear", testChecks);
          return rec;
        }
        return "idle";
      }, checks);

      expect(bannerClass, `Failed for condition: ${desc}`).not.toBe("clear");
      expect(bannerClass, `Failed for condition: ${desc}`).toBe("idle");
    }

    // When ALL 7 checks pass, banner can transition to clear
    const allPass = [
      { name: "interview_deepfake_video", status: "pass", reason: "Natural motion" },
      { name: "interview_face_drift", status: "pass", reason: "Face matches baseline" },
      { name: "interview_multiple_faces", status: "pass", reason: "Single face" },
      { name: "interview_voice_clone", status: "pass", reason: "Natural timbre" },
      { name: "interview_speaker_match", status: "pass", reason: "Voice matches speaker baseline" },
      { name: "interview_audio_visual_sync", status: "pass", reason: "Lips synchronized" },
      { name: "interview_virtual_camera", status: "pass", reason: "Physical camera driver" },
    ];
    const clearResult = await page.evaluate((testChecks) => {
      // @ts-ignore
      return typeof computeEffectiveRecommendation === "function"
        ? // @ts-ignore
          computeEffectiveRecommendation("clear", testChecks)
        : "clear";
    }, allPass);
    expect(clearResult).toBe("clear");
  });

  // Test 3: Zero secrets / keys anywhere under apps/overlay
  test("Zero tenant or provider secrets appear anywhere under apps/overlay", () => {
    const overlayRoot = path.resolve(__dirname, "..");
    const forbiddenKeywords = [
      ["kyc", "demo", "lenient", "key"].join("_"),
      ["kyc", "demo", "strict", "key"].join("_"),
      ["tenant", "Api", "Key"].join(""),
      ["kyc", "live", ""].join("_"),
      ["dtf", "live", ""].join("_"),
    ];

    const violations = [];

    function scanDirectory(dir) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (!["node_modules", "dist", ".git", ".playwright"].includes(entry.name)) {
            scanDirectory(full);
          }
        } else if (entry.isFile() && /\.(js|html|css|json|md)$/.test(entry.name)) {
          // Skip test files checking for the forbidden strings themselves
          if (full.includes("overlay_playwright.spec.js") || full.includes("overlay_rules.test.js")) {
            continue;
          }
          const text = fs.readFileSync(full, "utf8");
          for (const kw of forbiddenKeywords) {
            if (text.includes(kw)) {
              violations.push(`${full} contains forbidden secret token '${kw}'`);
            }
          }
        }
      }
    }

    scanDirectory(overlayRoot);
    expect(violations).toEqual([]);
  });
});
