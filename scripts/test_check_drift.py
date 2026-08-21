#!/usr/bin/env python3
"""Drift-gate self-check: python3 scripts/test_check_drift.py

Guards the behaviour the gate is actually for: warn-not-block by default, and
refusing to accept a doc edit that adds no content.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "check_drift.py"

# Hermetic: the fixture repo must not inherit the developer's git config.
# A global commit.gpgsign=true makes `git commit` block on a signing prompt,
# which would hang this test on any machine that signs commits.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}

ARCH = """---
module: pay
owner: UNKNOWN
---

# pay

## Rules

- never talks to the mailer directly
"""


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=GIT_ENV)


def run(root, *extra):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout


def setup(root: Path) -> None:
    (root / "src/pay").mkdir(parents=True)
    (root / "src/pay/pay.py").write_text("def charge():\n    pass\n")
    (root / "src/pay/CLAUDE.md").write_text("# Module: pay\n")
    (root / "src/pay/architecture.md").write_text(ARCH)
    (root / ".codedna").mkdir()
    (root / ".codedna/modules.json").write_text(
        '{"modules":[{"id":"pay","path":"src/pay",'
        '"claude":"src/pay/CLAUDE.md","architecture":"src/pay/architecture.md"}]}'
    )
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")


def main() -> int:
    root = Path(tempfile.mkdtemp())
    try:
        setup(root)

        code, out = run(root)
        assert code == 0 and "Drift: pass" in out, out

        # code moves, docs do not
        (root / "src/pay/pay.py").write_text("def charge(amount):\n    pass\n")
        code, out = run(root)
        assert "docs untouched" in out, out
        assert code == 0, f"default run must warn, not block: {code}"
        code, out = run(root, "--enforce")
        assert code == 1 and "Drift: fail" in out, out

        # the cheat: touch the doc without saying anything
        arch = root / "src/pay/architecture.md"
        arch.write_text(ARCH + "\n\n   \n")
        code, out = run(root, "--enforce")
        assert "say nothing new" in out, out
        assert code == 1, out

        # a real boundary added instead
        arch.write_text(ARCH + "- amounts are integer minor units, never floats\n")
        code, out = run(root, "--enforce")
        assert code == 0 and "Drift: pass" in out, out

        # machine-readable output for CI, same verdict as the text form
        import json as _json

        code, out = run(root, "--json")
        payload = _json.loads(out)
        assert payload["status"] == "pass" and payload["findings"] == [], out
        code, out = run(root, "--json", "--enforce")
        assert _json.loads(out)["status"] == "pass", out

        # a repo that never adopted CodeDNA is not a failing repo
        (root / ".codedna/modules.json").unlink()
        shutil.rmtree(root / "src/pay")
        code, out = run(root, "--enforce")
        assert code == 0 and "no modules found" in out.lower(), out
        # The escape hatch needs a deliberate marker with a reason. A PR
        # template documenting it — or a reviewer warning against it — used to
        # disable the gate repo-wide while CI still printed pass.
        from check_drift import SKIP_RE

        assert SKIP_RE.search("codedna: skip-docs vendored bump only")
        assert not SKIP_RE.search("- [ ] docs updated (or add `codedna: skip-docs`)")
        assert not SKIP_RE.search("please don't use codedna: skip-docs here")
        assert not SKIP_RE.search("codedna: skip-docs")  # no reason given

        # A subsystem owns files by glob across directories, and its rule file
        # is the doc that speaks for it.
        from check_drift import module_docs, module_files

        seam = {"id": "bridge", "paths": ["inc/**", "assets/js/**"],
                "rule": ".claude/rules/bridge.md"}
        changed = ["inc/a.php", "assets/js/b.js", "src/other.ts"]
        assert module_files(seam, changed) == ["inc/a.php", "assets/js/b.js"], seam
        assert module_docs(seam) == {".claude/rules/bridge.md"}

        # Tests and generated code move constantly without moving a boundary.
        # Demanding a doc edit for them is what taught people to use the hatch.
        from check_drift import DEFAULT_IGNORE, is_knowledge_file

        for quiet in ("svc/pay_test.go", "svc/api.pb.go", "svc/tests/helper.go", "svc/x.spec.ts"):
            assert not is_knowledge_file(quiet, DEFAULT_IGNORE), quiet
        assert is_knowledge_file("svc/pay.go", DEFAULT_IGNORE)

        # The two scripts keep separate ignore sets because CI fetches this file
        # alone. They must still agree.
        sys.path.insert(0, str(SCRIPT.parent))
        from detect_modules import BUILD_DIRS

        assert BUILD_DIRS == DEFAULT_IGNORE, BUILD_DIRS ^ DEFAULT_IGNORE
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("drift gate ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
