"""Download and verify pretrained model weights with pinned URLs and SHA-256 checksums."""
import hashlib
import os
from pathlib import Path
import sys
import time
import urllib.request
from typing import Dict, Any, List

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Pinned models with expected SHA-256 checksums and verified download locations
PINNED_MODELS: Dict[str, Dict[str, Any]] = {
    "face_landmarker.task": {
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        "product": "kyc",
        "description": "MediaPipe Face Landmarker (478 3D landmarks + 52 blendshapes)",
    },
    "minifasnet_v2.onnx": {
        "url": "https://huggingface.co/garciafido/minifasnet-v2-anti-spoofing-onnx/resolve/main/minifasnet_v2.onnx",
        "mirrors": [
            "https://media.githubusercontent.com/media/wequgy/RyouU/main/models/minifasnet_v2.onnx",
        ],
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


def _download_file(url: str, target: Path, max_retries: int = 3, timeout: int = 45) -> bool:
    """Download a file with retry logic and standard User-Agent."""
    temp_target = target.with_suffix(".tmp")
    headers = {"User-Agent": "Unclone-Model-Downloader/2.0 (Mozilla/5.0 compatible)"}

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(temp_target, "wb") as out:
                shutil_copy_chunks(resp, out)
            temp_target.replace(target)
            return True
        except Exception as e:
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
            print(f"  [RETRY {attempt}/{max_retries}] Download error from {url}: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return False


def shutil_copy_chunks(resp, out):
    while chunk := resp.read(65536):
        out.write(chunk)


def ensure_models_downloaded(product: str = "all", exit_on_failure: bool = False) -> bool:
    """Download missing model files and verify SHA-256 checksums."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    all_ok = True
    mirror_override = os.environ.get("MODEL_MIRROR_URL", "").strip()

    print(f"--- Model Verification & Download Pipeline [Product Scope: {product}] ---")

    for filename, meta in PINNED_MODELS.items():
        if product != "all" and meta["product"] != product:
            continue

        target = MODELS_DIR / filename
        expected_sha = meta["sha256"].lower()
        desc = meta.get("description", filename)

        # 1. If already on disk, check checksum
        if target.exists():
            actual_sha = compute_sha256(target)
            if actual_sha == expected_sha:
                print(f"[OK] {filename} ({desc}) -> SHA-256 verified ({actual_sha[:12]}...)")
                continue
            else:
                print(f"[WARN] {filename} SHA-256 mismatch (got {actual_sha}, expected {expected_sha}). Re-downloading...")
                target.unlink(missing_ok=True)

        # 2. Candidate download URLs
        candidate_urls: List[str] = []
        if mirror_override:
            candidate_urls.append(f"{mirror_override.rstrip('/')}/{filename}")
        candidate_urls.append(meta["url"])
        if "mirrors" in meta:
            candidate_urls.extend(meta["mirrors"])

        download_success = False
        for url in candidate_urls:
            print(f"[DOWNLOAD] Downloading {filename} from {url}...")
            if _download_file(url, target):
                actual_sha = compute_sha256(target)
                if actual_sha == expected_sha:
                    print(f"[OK] {filename} downloaded and verified (SHA-256: {actual_sha[:12]}...)")
                    download_success = True
                    break
                else:
                    target.unlink(missing_ok=True)
                    print(f"[ERROR] Checksum mismatch for {filename}: expected {expected_sha}, got {actual_sha}")

        if not download_success:
            print(f"[FAILED] Could not download and verify {filename} ({desc}) from any candidate mirror.")
            all_ok = False
            if exit_on_failure:
                sys.exit(1)

    print("--------------------------------------------------------------------------")
    return all_ok


if __name__ == "__main__":
    prod = sys.argv[1] if len(sys.argv) > 1 else "all"
    success = ensure_models_downloaded(prod, exit_on_failure=True)
    sys.exit(0 if success else 1)
