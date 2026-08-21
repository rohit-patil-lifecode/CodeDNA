#!/usr/bin/env python3
"""Claim-verification self-check: python3 scripts/test_verify_claims.py

Builds a repo containing one rule the code violates, one doc citing a
superseded ADR, and one claim nobody re-checked while the code moved on —
the three shapes of "no longer true" that the drift gate cannot see.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "verify_claims.py"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}

CLAUDE_MD = """# Module: pay

## Rules

- never import `mailer`; emit an event instead
- never import the billing helper directly

## Gotchas

- retries are capped at 3, see ADR-0003
"""

ARCH_MD = """---
module: pay
owner: platform
---

## Why it is this way

- split from orders, see ADR-0003
"""

ADR_3 = "# ADR 0003: retry policy\n\n- Status: superseded by ADR-0011\n"
ADR_11 = "# ADR 0011: replace retries with a queue\n\n- Status: accepted\n"


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
        (root / "src/pay").mkdir(parents=True)
        (root / "docs/decisions").mkdir(parents=True)
        (root / ".codedna").mkdir()
        # the code violates the first rule: it imports the very thing
        (root / "src/pay/pay.py").write_text("import mailer\n\n\ndef charge():\n    pass\n")
        (root / "src/pay/CLAUDE.md").write_text(CLAUDE_MD)
        (root / "src/pay/architecture.md").write_text(ARCH_MD)
        (root / "docs/decisions/0003-retry-policy.md").write_text(ADR_3)
        (root / "docs/decisions/0011-queue.md").write_text(ADR_11)
        (root / ".codedna/modules.json").write_text(json.dumps({"modules": [{
            "id": "pay", "path": "src/pay",
            "claude": "src/pay/CLAUDE.md",
            "architecture": "src/pay/architecture.md",
        }]}))
        git(root, "init", "-q", "-b", "main")
        git(root, "config", "user.email", "t@t")
        git(root, "config", "user.name", "t")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "init")

        code, out = run(root, "--json", "--stale-after", "0")
        payload = json.loads(out)
        kinds = {f["type"] for f in payload["findings"]}

        assert "violated" in kinds, f"missed the rule the code breaks: {out}"
        assert "superseded" in kinds, f"missed the superseded ADR citation: {out}"

        # a rule with no token to grep for is counted, not silently passed
        assert payload["rulesChecked"] == 1, payload
        assert payload["rulesStatedInProse"] == 1, payload

        # both docs citing ADR-0003 are flagged, not just one
        assert len([f for f in payload["findings"] if f["type"] == "superseded"]) == 2, out

        # unreviewed: move the code, leave the claims alone
        for i in range(3):
            (root / "src/pay/pay.py").write_text(f"import mailer\n\n\ndef charge():\n    x = {i}\n")
            git(root, "add", "-A")
            git(root, "commit", "-qm", f"change {i}")
        code, out = run(root, "--json", "--stale-after", "2")
        stale = [f for f in json.loads(out)["findings"] if f["type"] == "unreviewed"]
        assert stale, f"claims untouched across 3 code commits not flagged: {out}"

        # unreviewed alone must never fail a build; violated/superseded may
        code, _ = run(root, "--stale-after", "2")
        assert code == 0, "default run must report, not fail"
        code, _ = run(root, "--enforce", "--stale-after", "0")
        assert code == 1, "enforce must fail on violated/superseded"

        # a flow whose steps no longer resolve: the code moved, the documented
        # path did not, and Claude would follow a route that is not there
        (root / ".claude/rules").mkdir(parents=True)
        (root / "src/pay/registry.py").write_text("def dispatch():\n    pass\n")
        (root / ".claude/rules/charge.md").write_text(
            "---\npaths: [\"src/**\"]\n---\n# Flow: charge\n\n## Path\n\n"
            "1. `src/pay/registry.py` -> `dispatch()` — ok\n"
            "2. `src/pay/registry.py` -> `gone()` — symbol removed\n"
            "3. `src/pay/missing.py` -> `send()` — file removed\n"
        )
        git(root, "add", "-A")
        git(root, "commit", "-qm", "add flow")
        code, out = run(root, "--json", "--stale-after", "0")
        broken = [f for f in json.loads(out)["findings"] if f["type"] == "broken-flow"]
        assert len(broken) == 2, f"flow drift not caught exactly: {out}"
        code, _ = run(root, "--enforce", "--stale-after", "0")
        assert code == 1, "a broken flow must fail under --enforce"
        shutil.rmtree(root / ".claude")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "drop flow")

        # a clean repo passes
        (root / "src/pay/pay.py").write_text("def charge():\n    pass\n")
        (root / "src/pay/CLAUDE.md").write_text("# Module: pay\n\n## Rules\n\n- keep it simple\n")
        (root / "src/pay/architecture.md").write_text("---\nmodule: pay\n---\n")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "clean up")
        code, out = run(root, "--enforce", "--stale-after", "0")
        assert code == 0 and "Claims: pass" in out, out
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("claim verification ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
