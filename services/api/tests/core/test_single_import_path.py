"""Test that only a single, canonical import path for the application exists."""
import importlib
from pathlib import Path
import pytest
from fastapi import FastAPI


def test_root_facade_package_does_not_exist():
    """Verify that the legacy root app/ facade directory is deleted."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    root_app_dir = repo_root / "app"
    assert not root_app_dir.exists(), f"Legacy facade {root_app_dir} must not exist."


def test_canonical_import_path():
    """Verify that app is imported directly from the installed package."""
    import app.main
    assert hasattr(app.main, "app")
    assert isinstance(app.main.app, FastAPI)

    # Verify origin resolves inside services/api/app
    app_file = Path(app.main.__file__).resolve()
    assert "services" in app_file.parts and "api" in app_file.parts, (
        f"Expected app.main to resolve inside services/api/app, got: {app_file}"
    )


def test_no_alternate_services_api_import_path():
    """Verify that services.api.app is not a duplicate competing import path."""
    with pytest.raises((ModuleNotFoundError, ImportError)):
        importlib.import_module("services.api.app.main")
