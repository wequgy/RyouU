"""Drive one full verification against a RUNNING server, the way the verification page would.

  python -m scripts.e2e_demo --key kyc_demo_strict_key --id id.jpg --selfie me.jpg --audio clip.webm
  python -m scripts.e2e_demo --virtual-cam            # simulate an OBS virtual camera attack
  python -m scripts.e2e_demo --wrong-id-digits        # spoken ID digits don't match the ID

Server must run with KYC_DEV_MODE=1 (OTP codes echoed, transcripts accepted without Whisper).
Without --id/--selfie/--audio, tiny placeholder files are uploaded: those checks report 'uncertain'.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--key", default="kyc_demo_lenient_key")
    ap.add_argument("--id"), ap.add_argument("--selfie"), ap.add_argument("--audio")
    ap.add_argument("--virtual-cam", action="store_true")
    ap.add_argument("--wrong-id-digits", action="store_true")
    a = ap.parse_args()

    c = httpx.Client(base_url=a.base, timeout=120)
    expected = {"name": "Asha Rao", "dob": "1999-04-12", "id_last4": "4821"}
    r = c.post("/v1/verifications", headers={"Authorization": f"Bearer {a.key}"},
               json={"reference_id": f"e2e_{int(time.time())}", "expected": expected})
    r.raise_for_status()
    created = r.json()
    vid, token = created["id"], re.search(r"[?&]t=([^&]+)", created["flow_url"]).group(1)
    fh = {"X-Flow-Token": token}
    print("created", vid, "policy", created["policy"])

    def upload(kind, path, fallback_name, fallback_bytes):
        files = {"file": (Path(path).name, open(path, "rb"))} if path else {"file": (fallback_name, fallback_bytes)}
        c.post(f"/flow/{vid}/upload/{kind}", headers=fh, files=files).raise_for_status()

    upload("id_image", a.id, "id.jpg", b"placeholder")
    upload("selfie", a.selfie, "selfie.jpg", b"placeholder")
    upload("challenge_audio", a.audio, "clip.webm", b"placeholder")

    for ch, dest in (("email", "asha@example.com"), ("phone", "+919999999999")):
        code = c.post(f"/flow/{vid}/otp/send", headers=fh, json={"channel": ch, "destination": dest}).json()["dev_code"]
        c.post(f"/flow/{vid}/otp/verify", headers=fh, json={"channel": ch, "code": code}).raise_for_status()

    labels = ["OBS Virtual Camera"] if a.virtual_cam else ["FaceTime HD Camera"]
    c.post(f"/flow/{vid}/signals", headers=fh, json={"camera_labels": labels}).raise_for_status()

    chs = c.post(f"/flow/{vid}/challenges", headers=fh).json()["challenges"]
    metrics = {"head_turn": {"yaw_range_deg": 40, "face_present_ratio": 0.95},
               "hand_wave": {"occlusion_ratio": 0.3, "face_present_ratio_after": 0.95}, "phrase": {}}
    c.post(f"/flow/{vid}/challenges/result", headers=fh,
           json={"results": [{"id": x["id"], "metrics": metrics[x["type"]]} for x in chs]}).raise_for_status()
    code = next(x["expected_code"] for x in chs if x["type"] == "phrase")
    c.post(f"/flow/{vid}/transcripts", headers=fh, json={
        "name": "my name is Asha Rao", "dob": "12 April 1999",
        "id_last4": "nine nine nine nine" if a.wrong_id_digits else "four eight two one",
        "phrase": " ".join(code)}).raise_for_status()

    c.post(f"/flow/{vid}/submit", headers=fh).raise_for_status()
    for _ in range(60):
        res = c.get(f"/v1/verifications/{vid}", headers={"Authorization": f"Bearer {a.key}"}).json()
        if res["status"] != "processing":
            break
        time.sleep(1)
    print(json.dumps({k: res[k] for k in ("status", "decision", "trust", "reasons", "webhook")}, indent=2))
    for r in res["results"]:
        print(f"  {r['name']:<15} {r['status']:<10} trust={r['score']:.2f}  {r['reason']}")


if __name__ == "__main__":
    sys.exit(main())
