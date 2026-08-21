#!/usr/bin/env python3
"""Coupling self-check: python3 scripts/test_coupling.py

Builds a repo where two modules are secretly one subsystem — every change to
the backend layer also changes its frontend counterpart — plus an unrelated
module that changes alone. The seam must surface from history alone.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "coupling.py"
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=GIT_ENV)


def run(root, *extra):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout


def main() -> int:
    root = Path(tempfile.mkdtemp())
    try:
        for d in ("api", "web", "docs_site"):
            (root / d).mkdir()
            (root / d / "f.txt").write_text("0\n")
        (root / ".codedna").mkdir()
        (root / ".codedna/modules.json").write_text(json.dumps({"modules": [
            {"id": "api", "path": "api"},
            {"id": "web", "path": "web"},
            {"id": "docs_site", "path": "docs_site"},
        ]}))
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@t")
        git(root, "config", "user.name", "t")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "init")

        # api and web are one subsystem: every change touches both
        for i in range(6):
            (root / "api/f.txt").write_text(f"api {i + 1}\n")
            (root / "web/f.txt").write_text(f"web {i + 1}\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", f"feature {i}")
        # docs_site moves entirely on its own
        for i in range(4):
            (root / "docs_site/f.txt").write_text(f"docs {i + 1}\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", f"docs {i}")

        code, out = run(root, "--json")
        data = json.loads(out)

        seam_pairs = [set(s["modules"]) for s in data["seams"]]
        assert {"api", "web"} in seam_pairs, f"missed the seam: {out}"
        assert not any("docs_site" in p for p in seam_pairs), f"false seam: {out}"
        assert "docs_site" in data["orphans"], f"independent module not reported: {out}"

        # a declared subsystem must not be re-reported as an undeclared seam
        (root / ".codedna/modules.json").write_text(json.dumps({"modules": [
            {"id": "api", "path": "api"},
            {"id": "web", "path": "web"},
            {"id": "docs_site", "path": "docs_site"},
            {"id": "product", "kind": "subsystem", "members": ["api", "web"],
             "paths": ["api/**", "web/**"], "rule": ".claude/rules/product.md"},
        ]}))
        code, out = run(root, "--json")
        assert not json.loads(out)["seams"], f"declared seam still reported: {out}"

        # a repo with no history to read says so rather than inventing
        empty = Path(tempfile.mkdtemp())
        try:
            (empty / ".codedna").mkdir()
            (empty / ".codedna/modules.json").write_text('{"modules":[]}')
            git(empty, "init", "-q", "-b", "main")
            code, out = run(empty)
            assert code == 0 and "nothing to infer" in out.lower(), out
        finally:
            shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("coupling ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
