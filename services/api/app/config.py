"""Settings are read from the environment on every call, so tests can override them."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


def _num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


@dataclass
class Settings:
    data_dir: Path
    db_path: Path
    public_base_url: str
    flow_base_url: str
    cors_origins: list
    dev_mode: bool
    seed_demo: bool
    demo_webhook_url: str
    demo_webhook_secret: str
    flow_token_ttl_s: int
    otp_ttl_s: int
    otp_max_attempts: int
    otp_max_sends: int
    detectif_base_url: str
    detectif_api_key: str
    detectif_retry_sleep_cap_s: float
    detectif_max_attempts: int
    face_pass_sim: float
    face_fail_sim: float
    min_face_px: int
    whisper_model: str
    name_match_ratio: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_from: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    fast2sms_api_key: str
    webhook_max_attempts: int
    webhook_backoff_s: float
    challenge_ttl_s: int
    head_turn_min_yaw_deg: float
    hand_wave_min_occlusion: float
    min_face_present_ratio: float
    max_upload_mb: int
    focus_loss_review_count: int
    enforce_gates: bool
    strict_mode: bool
    enable_kyc: bool
    enable_interview: bool


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("KYC_DATA_DIR", "./data")).resolve()
    return Settings(
        data_dir=data_dir,
        db_path=Path(os.environ.get("KYC_DB_PATH", str(data_dir / "kyc.sqlite3"))),
        public_base_url=os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000"),
        flow_base_url=os.environ.get("FLOW_BASE_URL", "http://localhost:3000/verify"),
        cors_origins=[o.strip() for o in os.environ.get("KYC_CORS_ORIGINS", "*").split(",") if o.strip()],
        dev_mode=_flag("KYC_DEV_MODE", False),
        seed_demo=_flag("KYC_SEED_DEMO", False),
        strict_mode=_flag("KYC_STRICT", True),
        demo_webhook_url=os.environ.get("DEMO_WEBHOOK_URL", "http://localhost:9000/webhooks/kyc"),
        demo_webhook_secret=os.environ.get("DEMO_WEBHOOK_SECRET", "whsec_demo"),
        flow_token_ttl_s=int(_num("FLOW_TOKEN_TTL_S", 1800)),
        otp_ttl_s=int(_num("OTP_TTL_S", 300)),
        otp_max_attempts=int(_num("OTP_MAX_ATTEMPTS", 5)),
        otp_max_sends=int(_num("OTP_MAX_SENDS", 3)),
        detectif_base_url=os.environ.get("DETECTIF_BASE_URL", "https://platform.detectif.ai/v1").rstrip("/"),
        detectif_api_key=os.environ.get("DETECTIF_API_KEY", ""),
        detectif_retry_sleep_cap_s=_num("DETECTIF_RETRY_SLEEP_CAP_S", 5),
        detectif_max_attempts=int(_num("DETECTIF_MAX_ATTEMPTS", 3)),
        face_pass_sim=_num("FACE_PASS_SIM", 0.40),
        face_fail_sim=_num("FACE_FAIL_SIM", 0.25),
        min_face_px=int(_num("MIN_FACE_PX", 60)),
        whisper_model=os.environ.get("WHISPER_MODEL", "base.en"),
        name_match_ratio=int(_num("NAME_MATCH_RATIO", 80)),
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=int(_num("SMTP_PORT", 587)),
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_pass=os.environ.get("SMTP_PASS", ""),
        smtp_from=os.environ.get("SMTP_FROM", ""),
        twilio_account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.environ.get("TWILIO_FROM_NUMBER", ""),
        fast2sms_api_key=os.environ.get("FAST2SMS_API_KEY", ""),
        webhook_max_attempts=int(_num("WEBHOOK_MAX_ATTEMPTS", 3)),
        webhook_backoff_s=_num("WEBHOOK_BACKOFF_S", 1.0),
        challenge_ttl_s=int(_num("CHALLENGE_TTL_S", 60)),
        head_turn_min_yaw_deg=_num("HEAD_TURN_MIN_YAW_DEG", 25),
        hand_wave_min_occlusion=_num("HAND_WAVE_MIN_OCCLUSION", 0.15),
        min_face_present_ratio=_num("MIN_FACE_PRESENT_RATIO", 0.8),
        max_upload_mb=int(_num("MAX_UPLOAD_MB", 20)),
        focus_loss_review_count=int(_num("FOCUS_LOSS_REVIEW_COUNT", 3)),
        enforce_gates=_flag("KYC_ENFORCE_GATES", True),
        enable_kyc=_flag("ENABLE_KYC", True),
        enable_interview=_flag("ENABLE_INTERVIEW", True),
    )
