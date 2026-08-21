#!/usr/bin/env python3
"""Gap-finder self-check: python3 scripts/test_gaps.py

A module whose code is full of workarounds and whose Gotchas section is empty
is not simple, it is unwritten. That distinction is the whole point, so it has
to survive: a clean module must not be flagged, and documenting the trap must
clear the flag.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "gaps.py"

TRAPPY = """// HACK: same-origin iframe, strip injected nodes first
function sync() {
  setTimeout(() => flush(), 0);   // must run before the sheet is read
}
// do not remove: re-read after write
"""


def run(root, *extra):
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout


def main() -> int:
    root = Path(tempfile.mkdtemp())
    try:
        (root / "src/editor").mkdir(parents=True)
        (root / "src/calm").mkdir(parents=True)
        (root / ".codedna").mkdir()
        (root / "src/editor/canvas.js").write_text(TRAPPY)
        (root / "src/calm/math.js").write_text("export const add = (a, b) => a + b;\n")
        (root / "src/editor/CLAUDE.md").write_text("# editor\n\n## Gotchas\n")
        (root / "src/calm/CLAUDE.md").write_text("# calm\n\n## Rules\n\n- pure only\n")
        (root / ".codedna/modules.json").write_text(json.dumps({"modules": [
            {"id": "editor", "path": "src/editor", "claude": "src/editor/CLAUDE.md",
             "architecture": "src/editor/architecture.md"},
            {"id": "calm", "path": "src/calm", "claude": "src/calm/CLAUDE.md",
             "architecture": "src/calm/architecture.md"},
        ]}))

        code, out = run(root, "--json")
        data = json.loads(out)
        assert data["unwritten"] == ["editor"], f"wrong modules flagged: {out}"
        editor = next(m for m in data["modules"] if m["module"] == "editor")
        assert editor["evidence"] >= 3, editor
        assert editor["documented"] == 0, editor
        assert not any(m["module"] == "calm" for m in data["modules"]), \
            "a module with no traps must not be reported at all"

        # writing the gotcha down clears the flag
        (root / "src/editor/CLAUDE.md").write_text(
            "# editor\n\n## Gotchas\n\n"
            "- the preview iframe is same-origin, so injected nodes execute unless\n"
            "  stripped before `getOutput()`\n"
        )
        code, out = run(root, "--json")
        data = json.loads(out)
        assert data["unwritten"] == [], f"documenting the trap did not clear it: {out}"
        editor = next(m for m in data["modules"] if m["module"] == "editor")
        assert editor["documented"] > 0 and editor["evidence"] >= 3, editor

        # a comment block is not counted as documentation
        (root / "src/editor/CLAUDE.md").write_text(
            "# editor\n\n## Gotchas\n\n<!-- hunt for these, see the template -->\n"
        )
        code, out = run(root, "--json")
        assert json.loads(out)["unwritten"] == ["editor"], \
            f"template guidance counted as a written gotcha: {out}"
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("gap finder ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
