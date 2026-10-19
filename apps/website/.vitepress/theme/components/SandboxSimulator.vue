<template>
  <div class="sandbox-simulator">
    <div class="simulator-card">
      <h3 class="simulator-title">Select a Test Scenario</h3>

      <div class="scenario-buttons">
        <button
          @click="activeScenario = 'approved'"
          :class="['btn', activeScenario === 'approved' ? 'btn-primary' : 'btn-secondary']"
        >
          Scenario 1: Clean Approval
        </button>
        <button
          @click="activeScenario = 'review'"
          :class="['btn', activeScenario === 'review' ? 'btn-primary' : 'btn-secondary']"
        >
          Scenario 2: Needs Review (Deepfake Anomaly)
        </button>
        <button
          @click="activeScenario = 'rejected'"
          :class="['btn', activeScenario === 'rejected' ? 'btn-primary' : 'btn-secondary']"
        >
          Scenario 3: Hard Gate Rejection (Name Mismatch)
        </button>
      </div>

      <div class="code-grid">
        <div>
          <div class="code-label">Simulated Request (POST /v1/verifications)</div>
          <pre class="code-box"><code>{{ currentScenario.reqFormatted }}</code></pre>
        </div>

        <div>
          <div class="code-label">Simulated Response (final_decision ?? decision)</div>
          <pre class="code-box"><code>{{ currentScenario.resFormatted }}</code></pre>
        </div>
      </div>

      <div :class="['verdict-banner', currentScenario.bannerClass]">
        <span class="banner-text">{{ currentScenario.bannerText }}</span>
        <span :class="['status-chip', currentScenario.chipClass]">{{ currentScenario.chipText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

type ScenarioKey = 'approved' | 'review' | 'rejected';

const activeScenario = ref<ScenarioKey>('approved');

const scenarios = {
  approved: {
    req: {
      reference_id: "usr_test_01",
      expected: { name: "Sarah Connor", dob: "1984-02-28", id_last4: "9842" },
      policy: "strict"
    },
    res: {
      id: "ver_mock_001",
      status: "completed",
      decision: "approved",
      final_decision: null,
      trust: 0.94,
      reasons: [],
      checks: {
        id_details: { status: "pass", score: 0.98 },
        face_match: { status: "pass", score: 0.82, threshold: 0.40 },
        liveness: { status: "pass", reasons: ["blink_ok", "yaw_ok"] },
        anti_spoof: { status: "pass", score: 0.08, threshold: 0.50 }
      }
    },
    bannerText: "Verdict: APPROVED (All Hard Gates & Signals Passed)",
    bannerClass: "approved",
    chipClass: "approved",
    chipText: "Approved"
  },
  review: {
    req: {
      reference_id: "usr_test_02",
      expected: { name: "Alex Morgan", dob: "1995-08-20", id_last4: "4821" },
      policy: "strict"
    },
    res: {
      id: "ver_mock_002",
      status: "completed",
      decision: "needs_review",
      final_decision: null,
      trust: 0.65,
      reasons: ["video_deepfake_flagged", "passive_anti_spoof_uncalibrated"],
      checks: {
        id_details: { status: "pass", score: 0.95 },
        face_match: { status: "pass", score: 0.64, threshold: 0.40 },
        liveness: { status: "pass", reasons: ["blink_ok"] },
        video_deepfake: { status: "uncertain", score: 0.72, reasons: ["synthetic_probability_high"] }
      }
    },
    bannerText: "Verdict: NEEDS_REVIEW (Soft Signals Elevated -> Queued for Human Review)",
    bannerClass: "review",
    chipClass: "review",
    chipText: "Needs Review"
  },
  rejected: {
    req: {
      reference_id: "usr_test_03",
      expected: { name: "Johnathan Wick", dob: "1964-09-02", id_last4: "1911" },
      policy: "strict"
    },
    res: {
      id: "ver_mock_003",
      status: "completed",
      decision: "rejected_recommended",
      final_decision: null,
      trust: 0.12,
      reasons: ["id_details_name_mismatch", "face_match_failed"],
      checks: {
        id_details: { status: "fail", score: 0.32, reasons: ["name_mismatch"] },
        face_match: { status: "fail", score: 0.14, threshold: 0.25 }
      }
    },
    bannerText: "Verdict: REJECTED_RECOMMENDED (Hard Gate Name & Biometric Mismatch)",
    bannerClass: "rejected",
    chipClass: "flagged",
    chipText: "Rejected"
  }
};

const currentScenario = computed(() => {
  const s = scenarios[activeScenario.value];
  return {
    ...s,
    reqFormatted: JSON.stringify(s.req, null, 2),
    resFormatted: JSON.stringify(s.res, null, 2)
  };
});
</script>

<style scoped>
.sandbox-simulator {
  margin: 24px 0;
}
.simulator-card {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-card);
}
.simulator-title {
  margin-top: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--vp-c-text-1);
}
.scenario-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.scenario-buttons .btn {
  padding: 8px 16px;
  font-size: 13px;
}
.code-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 768px) {
  .code-grid {
    grid-template-columns: 1fr;
  }
}
.code-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--vp-c-text-3);
  margin-bottom: 8px;
}
.code-box {
  background: var(--surface-video);
  color: #E2E8F0;
  padding: 16px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  overflow-x: auto;
  margin: 0;
}
.verdict-banner {
  margin-top: 20px;
  padding: 14px 18px;
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid;
}
.verdict-banner.approved {
  background: var(--signal-clear-bg);
  border-color: var(--signal-clear-border);
}
.verdict-banner.approved .banner-text {
  color: var(--signal-clear);
  font-weight: 700;
}
.verdict-banner.review {
  background: var(--signal-caution-bg);
  border-color: var(--signal-caution-border);
}
.verdict-banner.review .banner-text {
  color: var(--signal-caution);
  font-weight: 700;
}
.verdict-banner.rejected {
  background: var(--signal-flag-bg);
  border-color: var(--signal-flag-border);
}
.verdict-banner.rejected .banner-text {
  color: var(--signal-flag);
  font-weight: 700;
}
</style>
