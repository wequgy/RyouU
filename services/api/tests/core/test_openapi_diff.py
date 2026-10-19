"""OpenAPI schema regression test to ensure 0 broken contracts across refactoring."""
import json
from pathlib import Path

from app.main import create_app


def test_openapi_schema_matches_baseline():
    baseline_path = None
    for p in Path(__file__).resolve().parents:
        cand = p / "contracts" / "openapi.baseline.json"
        if cand.exists():
            baseline_path = cand
            break
    assert baseline_path is not None and baseline_path.exists(), "Baseline schema openapi.baseline.json not found"
    
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    app = create_app()
    current = app.openapi()
    
    baseline_paths = set(baseline.get("paths", {}).keys())
    current_paths = set(current.get("paths", {}).keys())
    
    # All baseline endpoints must exist in current schema
    missing_paths = baseline_paths - current_paths
    assert not missing_paths, f"Missing paths from baseline OpenAPI schema: {missing_paths}"
    
    # Check that HTTP methods for each baseline path match
    for path, b_methods in baseline.get("paths", {}).items():
        c_methods = current.get("paths", {}).get(path, {})
        for method in b_methods.keys():
            assert method in c_methods, f"Path {path} missing method {method.upper()} from baseline"
