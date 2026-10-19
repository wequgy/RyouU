---
title: Candidate Consent & Transparency
description: Ethical guidelines, legal consent requirements, and privacy transparency for interview monitoring.
---

Continuous audio and video monitoring during job interviews touches candidate biometric rights under regulations such as the EU AI Act, GDPR, and Illinois BIPA.

---

## 1. Explicit Pre-Interview Consent Gate

The RyouU Overlay cannot begin recording without explicit participant acknowledgement.

Interviewers must verify that the candidate has agreed to integrity monitoring prior to toggling the monitoring switch:

1. **Invitation Notice**: The meeting invite must clearly disclose that the interview utilizes automated biometric verification and integrity monitoring.
2. **In-Call Confirmation**: The interviewer reads a standard disclosure:
   > *"Before we begin our discussion, I want to confirm that you consent to our automated audio and video verification to verify identity consistency throughout this session."*
3. **Consent Checkbox**: In the overlay HUD, the interviewer checks **"Candidate Consent Confirmed"** to unlock the **Start Auto-Monitor** action.

---

## 2. Privacy & Data Minimization

- **Region-Restricted Capture**: The overlay captures strictly the candidate's video tile inside the meeting window. It never records the interviewer's desktop, background applications, or personal files.
- **Local Storage**: Video clips and audio snippets are stored on the interviewer's local workstation or within your company's encrypted S3 storage bucket. They are never transmitted to unauthorized third parties.
- **Right to Human Explanation**: If an interview is terminated or an offer rescinded based partly on flagged signals, the hiring team must provide the candidate with human review findings rather than an automated rejection notification.
