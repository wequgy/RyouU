"""Application package for Unclone Suite API."""

# Enforce single canonical import path.
# Importing via services.api.app creates duplicate settings, DB handles, and model singletons.
if __name__ != "app":
    raise ImportError(
        f"Direct import of '{__name__}' is disabled. "
        "The application package must be imported strictly as 'app' (e.g., 'from app.main import app'). "
        "Install the package via 'pip install -e services/api'."
    )
