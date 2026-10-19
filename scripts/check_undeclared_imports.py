#!/usr/bin/env python3
"""Validate that every third-party import used across the codebase is explicitly declared in pyproject.toml,
and verify per-extra coverage for kyc-only and interview-only installations.
"""
import ast
import re
import sys
from pathlib import Path
from typing import Set, Dict, List

# Map top-level import names to package names as declared in pyproject.toml / requirements
IMPORT_TO_PKG: Dict[str, str] = {
    "cv2": "opencv-python-headless",
    "PIL": "pillow",
    "dotenv": "python-dotenv",
    "faster_whisper": "faster-whisper",
    "rapidocr_onnxruntime": "rapidocr-onnxruntime",
    "syncnet_python": "syncnet-python",
    "psycopg": "psycopg",
    "psycopg2": "psycopg",
    "yaml": "pyyaml",
    "starlette": "fastapi",
    "multipart": "python-multipart",
    "scenedetect": "scenedetect",
    "soundfile": "soundfile",
    "av": "av",
    "torch": "torch",
    "transformers": "transformers",
    "mediapipe": "mediapipe",
    "insightface": "insightface",
    "onnxruntime": "onnxruntime",
    "dateparser": "dateparser",
    "rapidfuzz": "rapidfuzz",
    "cryptography": "cryptography",
    "pydantic": "pydantic",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "numpy": "numpy",
    "pytest": "pytest",
    "pytest_asyncio": "pytest-asyncio",
    "requests": "requests",
    "scipy": "scipy",
    "argon2": "argon2-cffi",
}

# Directories to ignore during scanning
IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".agents",
    ".pytest_cache", "dist", "build", "ApexPay_Android"
}

# Known internal / local packages
LOCAL_PACKAGES = {
    "app", "tests", "scripts", "services", "sdk", "sdks", "unclone_kyc", "demo_client",
    "core", "kyc", "interview", "shared", "detectifai_verifier"
}


def parse_pyproject(pyproject_path: Path) -> tuple[Set[str], Dict[str, Set[str]]]:
    """Parse base dependencies and optional extras from pyproject.toml."""
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")
    
    content = pyproject_path.read_text(encoding="utf-8")
    base_deps = set()
    extras: Dict[str, Set[str]] = {}

    current_section = None
    in_dependencies = False

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[project.optional-dependencies]"):
            current_section = "optional"
            in_dependencies = False
            continue
        elif line.startswith("[") and not line.startswith("[project.optional-dependencies."):
            current_section = line.strip("[]")
            in_dependencies = False
            continue

        if current_section == "project" and line.startswith("dependencies = ["):
            in_dependencies = True
            continue

        if in_dependencies:
            if line.endswith("]"):
                in_dependencies = False
            dep_m = re.match(r'^["\']([a-zA-Z0-9_\-\.]+)', line)
            if dep_m:
                base_deps.add(dep_m.group(1).lower().replace("_", "-"))
            continue

        if current_section == "optional":
            extra_m = re.match(r"^([a-zA-Z0-9_\-]+)\s*=\s*\[(.*)", line)
            if extra_m:
                extra_name = extra_m.group(1)
                extras[extra_name] = set()
                rest = extra_m.group(2)
                for item in re.findall(r'["\']([a-zA-Z0-9_\-\.]+)', rest):
                    pkg = item.lower().replace("_", "-")
                    if not pkg.startswith("unclone-"):
                        extras[extra_name].add(pkg)
                if not line.endswith("]"):
                    current_section = f"optional.{extra_name}"
            continue

        if current_section and current_section.startswith("optional."):
            extra_name = current_section.split(".", 1)[1]
            if line.endswith("]"):
                current_section = "optional"
            for item in re.findall(r'["\']([a-zA-Z0-9_\-\.]+)', line):
                pkg = item.lower().replace("_", "-")
                if not pkg.startswith("unclone-"):
                    extras.setdefault(extra_name, set()).add(pkg)

    return base_deps, extras


def extract_imports_from_file(path: Path) -> Set[str]:
    """Extract top-level module names imported by a Python file."""
    imports = set()
    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
    except Exception as e:
        print(f"Warning: could not parse {path}: {e}", file=sys.stderr)
    return imports


def find_python_files(root: Path):
    """Find all Python files in the workspace excluding ignored directories."""
    for p in root.rglob("*.py"):
        if any(part in p.parts for part in IGNORE_DIRS):
            continue
        yield p


def verify_per_extra_coverage(root: Path, base_deps: Set[str], extras: Dict[str, Set[str]]) -> List[str]:
    """Ensure that kyc-only and interview-only routers have full coverage in their respective extras."""
    errors = []
    stdlib_modules = set(sys.stdlib_module_names)

    # 1. Structural requirements
    interview_deps = base_deps | extras.get("interview", set())
    kyc_deps = base_deps | extras.get("kyc", set())

    if "insightface" not in extras.get("interview", set()):
        errors.append("Interview extra is missing 'insightface' (required for interview face matching and second person checks).")
    if "onnxruntime" not in extras.get("interview", set()):
        errors.append("Interview extra is missing 'onnxruntime' (required for insightface runtime execution).")

    if "torch" in extras.get("kyc", set()):
        errors.append("KYC extra must NOT contain 'torch'; runtime must remain purely on ONNX Runtime.")

    # 2. Check imports in services/api/app/kyc/ against kyc_deps
    kyc_app_dir = root / "services" / "api" / "app" / "kyc"
    if kyc_app_dir.exists():
        for f in kyc_app_dir.glob("*.py"):
            for imp in extract_imports_from_file(f):
                if imp in stdlib_modules or imp in LOCAL_PACKAGES:
                    continue
                pkg = IMPORT_TO_PKG.get(imp, imp.lower().replace("_", "-"))
                if pkg not in kyc_deps:
                    errors.append(f"KYC file '{f.name}' imports '{imp}' (pkg '{pkg}') not declared in core/kyc extras.")

    # 3. Check imports in services/api/app/interview/ against interview_deps
    interview_app_dir = root / "services" / "api" / "app" / "interview"
    if interview_app_dir.exists():
        for f in interview_app_dir.glob("*.py"):
            for imp in extract_imports_from_file(f):
                if imp in stdlib_modules or imp in LOCAL_PACKAGES:
                    continue
                pkg = IMPORT_TO_PKG.get(imp, imp.lower().replace("_", "-"))
                if pkg not in interview_deps:
                    errors.append(f"Interview file '{f.name}' imports '{imp}' (pkg '{pkg}') not declared in core/interview extras.")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pyproject_file = root / "pyproject.toml"
    base_deps, extras = parse_pyproject(pyproject_file)
    all_declared = base_deps.copy()
    for extra_set in extras.values():
        all_declared |= extra_set

    # Also check services/api/pyproject.toml
    api_pyproject = root / "services" / "api" / "pyproject.toml"
    if api_pyproject.exists():
        api_base, api_extras = parse_pyproject(api_pyproject)
        all_declared |= api_base
        for s in api_extras.values():
            all_declared |= s

    stdlib_modules = set(sys.stdlib_module_names)
    undeclared = {}
    total_files = 0

    for py_file in find_python_files(root):
        # Skip dev-only scripts like convert_minifasnet.py from production dependency checks
        if py_file.name == "convert_minifasnet.py":
            continue
        total_files += 1
        file_imports = extract_imports_from_file(py_file)
        for imp in file_imports:
            if imp in stdlib_modules or imp in LOCAL_PACKAGES:
                continue

            pkg = IMPORT_TO_PKG.get(imp, imp.lower().replace("_", "-"))
            if pkg not in all_declared:
                undeclared.setdefault(pkg, []).append(f"{py_file.relative_to(root)} (imported '{imp}')")

    print(f"Scanned {total_files} Python files against declared dependencies across pyproject.toml.")

    has_error = False
    if undeclared:
        print("\nERROR: Found undeclared runtime imports in code:", file=sys.stderr)
        for pkg, usages in sorted(undeclared.items()):
            print(f"  [X] Package '{pkg}' is imported but not declared in pyproject.toml:", file=sys.stderr)
            for u in usages[:3]:
                print(f"       - {u}", file=sys.stderr)
        has_error = True

    # Run per-extra coverage verification
    extra_errors = verify_per_extra_coverage(root, base_deps, extras)
    if extra_errors:
        print("\nERROR: Per-extra dependency coverage violations:", file=sys.stderr)
        for err in extra_errors:
            print(f"  [X] {err}", file=sys.stderr)
        has_error = True

    if has_error:
        return 1

    print("SUCCESS: All runtime imports and per-extra coverage verified cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
