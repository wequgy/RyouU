"""Send one audio file to Detectif's deepfake endpoint and print the raw result.

  DETECTIF_API_KEY=dtf_live_... python -m scripts.detectif_cli clip.wav
Use it to settle questions early: does a 3-second clip work (their docs disagree: 4s vs 0.5s)?
How does a real recording compare with an XTTS / OpenVoice clone? How does phone-quality audio behave?
"""
import json
import sys

from app.checks.voice_ai import detect
from app.config import get_settings


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    s = get_settings()
    if not s.detectif_api_key:
        sys.exit("Set DETECTIF_API_KEY")
    print(json.dumps(detect(argv[1], "cli", s), indent=2))


if __name__ == "__main__":
    main(sys.argv)
