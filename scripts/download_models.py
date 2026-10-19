"""Download and verify pretrained model weights with pinned URLs and SHA-256 checksums."""
import hashlib
from pathlib import Path
import sys
import urllib.request

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Pinned models with expected SHA-256 checksums
PINNED_MODELS = {
    "face_landmarker.task": {
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
        "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        "product": "kyc",
        "description": "MediaPipe Face Landmarker (478 3D landmarks + 52 blendshapes)",
    },
    "minifasnet_v2.onnx": {
        "url": "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.onnx",
        "sha256": "d7b3cd9ba8a7ceb13baa8c4720902e27ca3112eff52f926c08804af6b6eecc7b",
        "product": "kyc",
        "description": "MiniFASNetV2 Passive Anti-Spoofing (Silent-Face)",
    },
}


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def ensure_models_downloaded(product: str = "all") -> bool:
    """Download missing model files and verify SHA-256 checksums."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    all_ok = True

    for filename, meta in PINNED_MODELS.items():
        if product != "all" and meta["product"] != product:
            continue

        target = MODELS_DIR / filename
        expected_sha = meta["sha256"].lower()

        if target.exists():
            actual_sha = compute_sha256(target)
            if actual_sha == expected_sha:
                print(f"[OK] {filename} verified (SHA-256 match)")
                continue
            else:
                print(f"[WARN] {filename} SHA-256 mismatch ({actual_sha} != {expected_sha}). Re-downloading...")
                target.unlink(missing_ok=True)

        print(f"[DOWNLOAD] Downloading {filename} from {meta['url']}...")
        try:
            req = urllib.request.Request(
                meta["url"],
                headers={"User-Agent": "Unclone-Model-Downloader/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(target, "wb") as out:
                out.write(resp.read())

            actual_sha = compute_sha256(target)
            if actual_sha != expected_sha:
                print(f"[ERROR] Downloaded {filename} failed SHA-256 validation: {actual_sha} != {expected_sha}")
                target.unlink(missing_ok=True)
                all_ok = False
            else:
                print(f"[OK] Downloaded and verified {filename}")
        except Exception as e:
            print(f"[ERROR] Failed to download {filename}: {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    prod = sys.argv[1] if len(sys.argv) > 1 else "all"
    success = ensure_models_downloaded(prod)
    sys.exit(0 if success else 1)
