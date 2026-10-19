"""Root compatibility facade for services/api/app."""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
_api_root = _repo_root / "services" / "api"
_api_app = _api_root / "app"

if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

__path__ = [str(_api_app)]

from services.api.app import *  # noqa: F401, F403
