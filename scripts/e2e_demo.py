"""Drive full verification sessions against a RUNNING server or execute automated attack scenarios.

Usage:
  python -m scripts.e2e_demo --all-scenarios
  python -m scripts.e2e_demo --key kyc_demo_strict_key --id id.jpg --selfie me.jpg --audio clip.webm
  python -m scripts.e2e_demo --virtual-cam
  python -m scripts.e2e_demo --wrong-id-digits

Server must run with KYC_DEV_MODE=1 (OTP dev_code echoed).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx


def run_session(client, key, scenario_name, *,
                id_bytes=None, id_name="id.jpg",
                selfie_bytes=None, selfie_name="me.jpg",
                audio_bytes=None, audio_name="clip.webm",
                video_bytes=None, video_name="video.webm",
                expected=None, signals=None, wrong_transcripts=False):
    expected = expected or {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}
    r = client.post("/v1/verifications", headers={"Authorization": f"Bearer {key}"},
                    json={"reference_id": f"scen_{int(time.time()*1000)%1000000}", "expected": expected})
    if r.status_code != 201:
        return {"scenario": scenario_name, "stage": "create", "status_code": r.status_code, "decision": "blocked", "reason": r.text}
    created = r.json()
    vid, token = created["id"], re.search(r"[?&]t=([^&]+)", created["flow_url"]).group(1)
    fh = {"X-Flow-Token": token}

    # 1. ID Upload
    f_id = {"file": (id_name, id_bytes or b"dummy_id_image_data")}
    r_id = client.post(f"/flow/{vid}/upload/id_image", headers=fh, files=f_id)
    if r_id.status_code != 200:
        return {"scenario": scenario_name, "stage": "id_gate", "status_code": r_id.status_code, "decision": "blocked_gate", "reason": r_id.json().get("detail", r_id.text)}

    # 2. Selfie Upload
    f_selfie = {"file": (selfie_name, selfie_bytes or b"dummy_selfie_data")}
    r_selfie = client.post(f"/flow/{vid}/upload/selfie", headers=fh, files=f_selfie)
    if r_selfie.status_code != 200:
        return {"scenario": scenario_name, "stage": "selfie_gate", "status_code": r_selfie.status_code, "decision": "blocked_gate", "reason": r_selfie.json().get("detail", r_selfie.text)}

    # 3. Audio & Video
    if audio_bytes:
        client.post(f"/flow/{vid}/upload/challenge_audio", headers=fh, files={"file": (audio_name, audio_bytes)})
    if video_bytes:
        client.post(f"/flow/{vid}/upload/challenge_video", headers=fh, files={"file": (video_name, video_bytes)})

    # 4. OTPs
    for ch, dest in (("email", "asha@example.com"), ("phone", "+919999999999")):
        res_otp = client.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": ch, "destination": dest})
        if res_otp.status_code == 200:
            dev_code = res_otp.json().get("dev_code")
            if dev_code:
                client.post(f"/flow/{vid}/otp/verify", headers=fh, json={"channel": ch, "code": dev_code})

    # 5. Signals
    client.post(f"/flow/{vid}/signals", headers=fh, json=signals or {"camera_labels": ["FaceTime HD Camera"]})

    # 6. Challenges
    r_ch = client.post(f"/flow/{vid}/challenges", headers=fh)
    if r_ch.status_code == 200:
        chs = r_ch.json().get("challenges", [])
        metrics = {"head_turn": {"yaw_range_deg": 38, "face_present_ratio": 0.95}}
        client.post(f"/flow/{vid}/challenges/result", headers=fh,
                    json={"results": [{"id": x["id"], "metrics": metrics.get(x["type"], {})} for x in chs]})
        phrase_ch = next((x for x in chs if x["type"] == "phrase"), None)
        code = phrase_ch["expected_code"] if phrase_ch else "4821"
        words = " ".join(phrase_ch.get("expected_words", [])) if phrase_ch else ""
        phrase_val = f"{words} {' '.join(code)}".strip()

        client.post(f"/flow/{vid}/transcripts", headers=fh, json={
            "name": "my name is Asha Rao",
            "dob": "12 April 1999",
            "id_last4": "0000" if wrong_transcripts else "4821",
            "phrase": phrase_val
        })

    # 7. Submit
    client.post(f"/flow/{vid}/submit", headers=fh)

    # 8. Poll result
    for _ in range(40):
        res = client.get(f"/v1/verifications/{vid}", headers={"Authorization": f"Bearer {key}"}).json()
        if res.get("status") != "processing":
            break
        time.sleep(1)

    return {
        "scenario": scenario_name,
        "vid": vid,
        "status": res.get("status"),
        "decision": res.get("final_decision") or res.get("decision"),
        "reasons": res.get("reasons", []),
        "trust": res.get("trust"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--key", default="kyc_demo_strict_key")
    ap.add_argument("--all-scenarios", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--selfie")
    ap.add_argument("--audio")
    ap.add_argument("--virtual-cam", action="store_true")
    ap.add_argument("--wrong-id-digits", action="store_true")
    a = ap.parse_args()

    c = httpx.Client(base_url=a.base, timeout=60)

    id_data = Path(a.id).read_bytes() if a.id else (Path("id.jpeg").read_bytes() if Path("id.jpeg").exists() else None)
    selfie_data = Path(a.selfie).read_bytes() if a.selfie else (Path("selfie1.jpg").read_bytes() if Path("selfie1.jpg").exists() else None)
    other_face_data = Path("other_person.jpeg").read_bytes() if Path("other_person.jpeg").exists() else None

    if a.all_scenarios:
        print("=" * 85)
        print("Running RyouU KYC Scripted Attack Scenarios Suite...")
        print("=" * 85)

        results = []

        # Scenario 1: Wrong ID Details (OCR gate blocks mismatched name)
        r1 = run_session(c, a.key, "Wrong ID Details", id_bytes=id_data,
                         expected={"name": "Mismatched Person", "dob": "1990-01-01", "id_last4": "9999"})
        results.append(r1)

        # Scenario 2: Different-Person / Mismatched Selfie (Selfie gate blocks)
        r2 = run_session(c, a.key, "Different-Person Selfie", id_bytes=id_data, selfie_bytes=other_face_data,
                         expected={"name": "Etta", "dob": "2012-03-31", "id_last4": "28"})
        results.append(r2)

        # Scenario 3: Virtual Camera Injection (Flagged in source checks)
        selfie_vcam = (selfie_data + b"\x01") if selfie_data else None
        r3 = run_session(c, a.key, "Virtual Camera (OBS)", id_bytes=id_data, selfie_bytes=selfie_vcam,
                         expected={"name": "Etta", "dob": "2012-03-31", "id_last4": "28"},
                         signals={"camera_labels": ["OBS Virtual Camera", "v4l2loopback"]})
        results.append(r3)

        # Scenario 4: Spoken Digits Mismatch (Voice / transcripts mismatch)
        selfie_digits = (selfie_data + b"\x02") if selfie_data else None
        r4 = run_session(c, a.key, "Spoken Digits Mismatch", id_bytes=id_data, selfie_bytes=selfie_digits,
                         expected={"name": "Etta", "dob": "2012-03-31", "id_last4": "28"},
                         wrong_transcripts=True)
        results.append(r4)

        # Scenario 5: Replayed Media Across Sessions (Replays selfie from Scenario 3)
        r5 = run_session(c, a.key, "Replayed Selfie Attack", id_bytes=id_data, selfie_bytes=selfie_vcam,
                         expected={"name": "Etta", "dob": "2012-03-31", "id_last4": "28"})
        results.append(r5)

        # Print Markdown Table
        print()
        print("| Attack / Test Scenario | Enforcement Stage | Final Recommendation | Reason / Signal Detected |")
        print("| :--- | :--- | :--- | :--- |")
        for r in results:
            scen = r.get("scenario", "—")
            stage = r.get("stage", "completed")
            dec = r.get("decision", "—")
            reasons = r.get("reason") or (", ".join(r.get("reasons", [])) if r.get("reasons") else "—")
            print(f"| **{scen}** | `{stage}` | `{dec}` | {reasons[:60]} |")
        print("=" * 85)
        return

    # Single interactive demo
    sig = {"camera_labels": ["OBS Virtual Camera"]} if a.virtual_cam else None
    res = run_session(c, a.key, "Single Run", signals=sig, wrong_transcripts=a.wrong_id_digits)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
