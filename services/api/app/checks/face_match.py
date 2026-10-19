"""Face match: ID photo vs live selfie. InsightFace buffalo_l (SCRFD detector + ArcFace).

NOTE: buffalo_l weights are research / non-commercial only. Thresholds are PLACEHOLDERS:
calibrate FACE_PASS_SIM / FACE_FAIL_SIM on your own ID-photo vs selfie pairs (scripts/face_cli.py).
"""
import numpy as np

from ..models import CheckContext, CheckResult
from .base import register

_APP = None


def _load_app():
    global _APP
    if _APP is None:
        from insightface.app import FaceAnalysis  # heavy import, kept lazy
        app = FaceAnalysis(name="buffalo_l")
        app.prepare(ctx_id=-1, det_size=(640, 640))  # -1 = CPU; use 0 for GPU
        _APP = app
    return _APP


def embed_image(path):
    """Return (embedding or None, meta). The largest face in the image is used."""
    import cv2
    img = cv2.imread(str(path))
    if img is None:
        return None, {"error": "unreadable image"}
    faces = _load_app().get(img)
    if not faces:
        return None, {"error": "no face detected"}
    f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return f.normed_embedding, {"face_px": int(f.bbox[2] - f.bbox[0]), "n_faces": len(faces),
                                "det_score": float(f.det_score)}


EMBEDDER = embed_image  # replaceable in tests


def classify(sim: float, pass_sim: float, fail_sim: float):
    """Return (status, trust score, confidence) for a cosine similarity."""
    span = max(pass_sim - fail_sim, 1e-6)
    score = min(1.0, max(0.0, (sim - fail_sim) / span))
    if sim >= pass_sim:
        return "pass", score, min(1.0, 0.6 + (sim - pass_sim) * 2)
    if sim <= fail_sim:
        return "fail", score, min(1.0, 0.6 + (fail_sim - sim) * 2)
    return "uncertain", score, 0.3


def verify_face_match(id_path, selfie_path, s) -> CheckResult:
    if not id_path or not selfie_path:
        return CheckResult.skipped("face_match", "ID image or selfie not provided")
    try:
        e_id, m_id = EMBEDDER(id_path)
        e_self, m_self = EMBEDDER(selfie_path)
    except ImportError:
        return CheckResult.uncertain("face_match", "Face model not installed (pip install -r requirements-ml.txt)")
    if e_id is None:
        return CheckResult.uncertain("face_match", f"ID image problem: {m_id.get('error')}", **{"id": m_id})
    if e_self is None:
        return CheckResult.uncertain("face_match", f"Selfie problem: {m_self.get('error')}", selfie=m_self)
    if m_id["face_px"] < s.min_face_px or m_self["face_px"] < s.min_face_px:
        return CheckResult.uncertain("face_match", f"Face too small (min {s.min_face_px}px)", id=m_id, selfie=m_self)
    if m_self.get("n_faces", 1) > 1:
        return CheckResult.uncertain("face_match", "Multiple faces in selfie", selfie=m_self)
    sim = float(np.dot(e_id, e_self))
    status, score, conf = classify(sim, s.face_pass_sim, s.face_fail_sim)
    reason = {"pass": f"Face matches ID (similarity {sim:.2f})",
              "fail": f"Face does not match ID (similarity {sim:.2f})",
              "uncertain": f"Borderline face similarity {sim:.2f}"}[status]
    return CheckResult(name="face_match", status=status, score=score, confidence=conf, reason=reason,
                       details={"similarity": round(sim, 4), "id": m_id, "selfie": m_self})


@register("face_match")
def face_match(ctx: CheckContext) -> CheckResult:
    return verify_face_match(ctx.files.get("id_image"), ctx.files.get("selfie"), ctx.settings)
