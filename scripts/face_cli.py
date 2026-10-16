"""Compare two face images (ID photo vs selfie). Use this to calibrate FACE_PASS_SIM / FACE_FAIL_SIM.

  python -m scripts.face_cli id.jpg selfie.jpg [more_selfie.jpg ...]
Needs: pip install -r requirements-ml.txt
"""
import sys

import numpy as np

from app.checks.face_match import classify, embed_image
from app.config import get_settings


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    s = get_settings()
    ref, meta = embed_image(argv[1])
    if ref is None:
        sys.exit(f"{argv[1]}: {meta}")
    print(f"reference {argv[1]}: {meta}")
    for path in argv[2:]:
        emb, m = embed_image(path)
        if emb is None:
            print(f"{path}: {m}")
            continue
        sim = float(np.dot(ref, emb))
        status, score, conf = classify(sim, s.face_pass_sim, s.face_fail_sim)
        print(f"{path}: similarity={sim:.3f} -> {status} (thresholds fail<={s.face_fail_sim} pass>={s.face_pass_sim}) {m}")


if __name__ == "__main__":
    main(sys.argv)
