"""Root entrypoint forwarding to services/api/app/main.py."""
import sys
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent / "services" / "api"
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from services.api.app.main import app, create_app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
