---
title: Interactive Sandbox Simulator
description: Test verification workflows and decision logic against simulated scenarios with zero server setup.
---

# Interactive Sandbox Simulator

::: info SIMULATION ENVIRONMENT
This interactive sandbox runs entirely in your browser using mock data and simulated API responses. It does not contact a live server or upload biometric media.
:::

Use this simulator to explore how the server evaluates verification inputs, computes trust scores, and generates decision states.

---

<SandboxSimulator />

---

## Decision Logic Breakdown

1. **`approved`**: When all hard gates (ID details matching, face distance above threshold) pass and soft signals show low anomaly probability.
2. **`needs_review`**: When any probabilistic AI model (visual deepfake classifier, voice clone detection, passive anti-spoofing) detects uncertainty. The verification is held for a human compliance officer to inspect.
3. **`rejected_recommended`**: Only issued when a strict, objective hard gate is violated (name mismatch, DOB mismatch, or failed SMS OTP). Soft models never issue autonomous denials.
