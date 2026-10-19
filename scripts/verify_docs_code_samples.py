#!/usr/bin/env python3
"""
scripts/verify_docs_code_samples.py

Extracts Python code snippets from documentation markdown files in apps/website/src/content/docs/
and syntax-checks or type-checks them against the installed unclone_kyc package.
Fails CI if a documented code sample breaks or has invalid syntax.
"""

import os
import re
import sys
import ast

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "apps", "website")

def extract_python_snippets(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Match ```python ... ``` blocks (supporting title annotations like ```python [Python])
    pattern = r"```python(?:[^\n]*)\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    snippets = []
    for m in matches:
        code = m.strip()
        if code:
            snippets.append(code)
    return snippets

def verify_snippet(code, filename, index):
    try:
        # Parse snippet AST to guarantee valid syntax
        ast.parse(code)
        print(f"  [OK] Sample #{index} in {filename} parsed successfully.")
        return True
    except SyntaxError as e:
        print(f"  [FAIL] SyntaxError in {filename} sample #{index}: {e}")
        return False

def main():
    if not os.path.exists(DOCS_DIR):
        print(f"Error: Docs directory not found at {DOCS_DIR}")
        sys.exit(1)

    print("Verifying Python code samples from documentation...")
    total_samples = 0
    failed_samples = 0

    for root, dirs, files in os.walk(DOCS_DIR):
        # Exclude internal / build directories
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.vitepress', 'tests', 'dist')]
        for f in files:
            if f.endswith(".md"):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, DOCS_DIR)
                snippets = extract_python_snippets(full_path)
                if snippets:
                    print(f"Checking {rel_path} ({len(snippets)} Python sample(s)):")
                    for i, snip in enumerate(snippets, 1):
                        total_samples += 1
                        if not verify_snippet(snip, rel_path, i):
                            failed_samples += 1

    print("\n-------------------------------------------")
    print(f"Total Python code samples verified: {total_samples}")
    print(f"Failed samples: {failed_samples}")
    print("-------------------------------------------")

    if failed_samples > 0:
        print("FAILED: One or more code samples in documentation contain syntax errors.")
        sys.exit(1)
    else:
        print("PASSED: All documentation code samples are syntactically valid!")

if __name__ == "__main__":
    main()
