#!/usr/bin/env python3
"""Validate that every third-party import used across the codebase is explicitly declared in pyproject.toml."""
import ast
import re
import sys
from pathlib import Path
from typing import Set, Dict

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


def parse_declared_dependencies(pyproject_path: Path) -> Set[str]:
    """Parse declared dependencies from pyproject.toml including all extras."""
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")
    
    content = pyproject_path.read_text(encoding="utf-8")
    declared = set()
    
    # Matches items inside dependencies = [...] or extras = [...]
    dep_regex = re.compile(r'^\s*["\']([a-zA-Z0-9_\-\.]+)(?:\[.*?\])?(?:[<>=~!].*?)?["\'],?', re.MULTILINE)
    for match in dep_regex.finditer(content):
        pkg_name = match.group(1).lower().replace("_", "-")
        # filter out section markers or internal self-references
        if not pkg_name.startswith("unclone-suite"):
            declared.add(pkg_name)
    
    return declared


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


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pyproject_file = root / "pyproject.toml"
    declared_pkgs = parse_declared_dependencies(pyproject_file)
    
    # Python stdlib modules
    stdlib_modules = set(sys.stdlib_module_names)
    
    undeclared = {}
    total_files = 0
    
    for py_file in find_python_files(root):
        total_files += 1
        file_imports = extract_imports_from_file(py_file)
        for imp in file_imports:
            if imp in stdlib_modules or imp in LOCAL_PACKAGES:
                continue
            
            pkg = IMPORT_TO_PKG.get(imp, imp.lower().replace("_", "-"))
            if pkg not in declared_pkgs:
                undeclared.setdefault(pkg, []).append(f"{py_file.relative_to(root)} (imported '{imp}')")
    
    print(f"Scanned {total_files} Python files against {len(declared_pkgs)} declared packages in pyproject.toml.")
    
    if undeclared:
        print("\nERROR: Found undeclared runtime imports in code:", file=sys.stderr)
        for pkg, usages in sorted(undeclared.items()):
            print(f"  [X] Package '{pkg}' is imported but not declared in pyproject.toml:", file=sys.stderr)
            for u in usages[:3]:
                print(f"       - {u}", file=sys.stderr)
            if len(usages) > 3:
                print(f"       - ... and {len(usages) - 3} more", file=sys.stderr)
        print("\nFix: Declare these packages in pyproject.toml (under dependencies or optional-dependencies).", file=sys.stderr)
        return 1
    
    print("SUCCESS: All runtime imports are declared in pyproject.toml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
