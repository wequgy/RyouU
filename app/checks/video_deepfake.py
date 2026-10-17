"""Video deepfake check: sample frames, crop the face, score each crop with a pretrained ViT image detector.

Model: prithivMLmods/Deep-Fake-Detector-v2-Model (ViT-base, "Realism" vs "Deepfake").
It is an IMAGE classifier trained on one dataset and may not generalise to other fakes (face swaps,
new generators). Treat the score as a weak signal: it can only push a session to needs_review, never reject.
Without a video it falls back to the selfie so the check can be tested before the page exists.
"""
import os

from ..models import CheckContext, CheckResult
from .base import register
from . import face_match

MODEL_ID = os.environ.get("DEEPFAKE_MODEL", "prithivMLmods/Deep-Fake-Detector-v2-Model")
N_FRAMES = 4
MIN_FACES = 2          # fewer usable face crops than this -> uncertain
_M = None


def _thr():
    return (float(os.environ.get("DEEPFAKE_PASS", "0.85")), float(os.environ.get("DEEPFAKE_FAIL", "0.90")))


def _load():
    global _M
    if _M is None:
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        proc = AutoImageProcessor.from_pretrained(MODEL_ID)
        model = AutoModelForImageClassification.from_pretrained(MODEL_ID).eval()
        fake_idx = next(int(i) for i, lab in model.config.id2label.items() if "fake" in str(lab).lower())
        _M = (proc, model, fake_idx)
    return _M


def sample_frames(path, n=N_FRAMES, step=5, max_read=450):
    """Read every `step`-th frame, return n spread evenly. PyAV fallback for fragmented video."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    cands, i = [], 0
    while i < max_read and cap.grab():
        if i % step == 0:
            ok, f = cap.retrieve()
            if ok:
                cands.append(f)
        i += 1
    cap.release()
    if not cands:
        try:
            import av
            with av.open(str(path)) as container:
                if container.streams.video:
                    v_stream = container.streams.video[0]
                    for j, frame in enumerate(container.decode(v_stream)):
                        if j >= max_read:
                            break
                        if j % step == 0:
                            cands.append(frame.to_ndarray(format="bgr24"))
        except Exception:
            pass
    if len(cands) <= n:
        return cands
    idx = [round(k * (len(cands) - 1) / (n - 1)) for k in range(n)]
    return [cands[k] for k in idx]


def face_crops(frames, margin=0.25):
    """Largest face per frame, cropped with a margin. Frames without a face are dropped."""
    app, out = face_match._load_app(), []
    for img in frames:
        faces = app.get(img)
        if not faces:
            continue
        f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        x1, y1, x2, y2 = f.bbox
        w, h = x2 - x1, y2 - y1
        H, W = img.shape[:2]
        x1, y1 = max(0, int(x1 - w * margin)), max(0, int(y1 - h * margin))
        x2, y2 = min(W, int(x2 + w * margin)), min(H, int(y2 + h * margin))
        if x2 > x1 and y2 > y1:
            out.append(img[y1:y2, x1:x2])
    return out


def score_frames(crops) -> list:
    """Fake probability (0..1) for each BGR face crop."""
    import torch
    from PIL import Image
    proc, model, fake_idx = _load()
    imgs = [Image.fromarray(c[:, :, ::-1]) for c in crops]
    with torch.no_grad():
        logits = model(**proc(images=imgs, return_tensors="pt")).logits
    return torch.softmax(logits, dim=-1)[:, fake_idx].tolist()


@register("video_deepfake")
def video_deepfake(ctx: CheckContext) -> CheckResult:
    import cv2
    video, selfie = ctx.files.get("challenge_video"), ctx.files.get("selfie")
    src = video or selfie
    if not src:
        return CheckResult.skipped("video_deepfake", "No video or selfie provided")
    source = "video" if video else "selfie"
    try:
        frames = sample_frames(src) if video else [cv2.imread(str(selfie))]
        frames = [f for f in frames if f is not None]
        crops = face_crops(frames)
        need = MIN_FACES if video else 1
        if len(crops) < need:
            return CheckResult.uncertain("video_deepfake", f"Only {len(crops)} usable face frame(s) in the {source}",
                                         source=source, frames_read=len(frames))
        probs = score_frames(crops)
    except ImportError:
        return CheckResult.uncertain("video_deepfake", "torch/transformers not installed (pip install torch transformers)")
    mean_p, max_p = sum(probs) / len(probs), max(probs)
    pass_t, fail_t = _thr()
    details = {"source": source, "model": MODEL_ID, "frames_scored": len(probs), "mean_fake": round(mean_p, 4),
               "max_fake": round(max_p, 4), "per_frame": [round(p, 3) for p in probs]}
    trust = round(1.0 - mean_p, 4)
    if mean_p >= fail_t:
        return CheckResult("video_deepfake", "fail", trust, 0.5, f"Face looks synthetic (confidence {mean_p:.2f})", details)
    return CheckResult("video_deepfake", "pass", trust, 0.5, f"No deepfake signal (mean fake {mean_p:.2f})", details)