from app.checks import face_match, spoken_details

face_match._load_app()
print("face model ready")

from faster_whisper import WhisperModel
from app.config import get_settings
WhisperModel(get_settings().whisper_model, device="auto", compute_type="int8")
print("whisper ready")