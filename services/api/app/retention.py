"""Data retention policy and cleanup jobs.

Deletes verifications and associated encrypted evidence after a configurable retention window.
"""
import shutil
import time

from . import db
from .config import get_settings


def cleanup_expired_verifications(max_age_s: float = 30 * 86400) -> int:
    """Delete verifications and associated uploaded files older than max_age_s."""
    s = get_settings()
    expired_ids = db.get_expired_verifications(max_age_s)
    count = 0
    for vid in expired_ids:
        # 1. Remove filesystem artifacts
        folder = s.data_dir / "uploads" / vid
        shutil.rmtree(folder, ignore_errors=True)
        # 2. Remove DB records
        db.delete_verification(vid)
        count += 1
    return count
