#!/usr/bin/env python3
"""Detection self-check: python3 scripts/test_detect_modules.py

Guards the three ways detection produced confidently-wrong module lists:
a real package named docs/ or tests/ vanishing, an MVC layer scored as a
bounded module, and a workspace scope folder hiding the packages inside it.
"""

import shutil
import tempfile
from pathlib import Path

from detect_modules import detect

TREE = [
    # turborepo: apps/docs and packages/tests are real packages, not support folders
    "apps/docs/package.json",
    "apps/docs/app/page.tsx",
    "apps/web/package.json",
    "apps/web/app/page.tsx",
    "packages/tests/package.json",
    "packages/tests/index.ts",
    # scoped workspace package, one level deeper
    "packages/scope/ui/package.json",
    "packages/scope/ui/index.tsx",
    # a package whose own tests/ must not count as its source
    "packages/util/package.json",
    "packages/util/tests/util_test.ts",
    # laravel: technical layers, not bounded modules
    "app/Http/Controllers/UserController.php",
    "app/Services/BillingService.php",
    "app/Services/EmailService.php",
    "app/Services/AuthService.php",
    "app/Services/PdfService.php",
    # go service detected by entrypoint
    "services/api/main.go",
    "services/api/handler.go",
    "node_modules/junk/index.js",
]


def build(root: Path) -> None:
    for rel in TREE:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"name":"pkg"}' if p.name == "package.json" else "")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        build(tmp)
        found = {m["path"]: (m["confidence"], m["reason"]) for m in detect(tmp)["modules"]}

        for pkg in ("apps/docs", "apps/web", "packages/tests", "packages/scope/ui"):
            assert found.get(pkg) == ("high", "manifest"), f"{pkg} lost: {found.get(pkg)}"

        assert "packages/scope" not in found, "scope folder reported instead of its packages"
        assert found.get("services/api") == ("high", "entrypoint"), found.get("services/api")

        for layer in ("app/Http", "app/Services"):
            conf, reason = found.get(layer, ("missing", "missing"))
            assert conf == "low" and reason == "layer-smell", f"{layer} scored {conf}/{reason}"

        assert not any(p.startswith("node_modules") for p in found), found
        # a package is not demoted by its own tests/ folder
        assert "packages/util" in found, found

        # Two developers regenerating this on different days must produce
        # byte-identical output, or every branch carries a merge conflict.
        import json

        first, second = json.dumps(detect(tmp)), json.dumps(detect(tmp))
        assert first == second, "detect() is not deterministic"
        assert "generated_at" not in first, "timestamp back in modules.json"
        paths = [m["path"] for m in json.loads(first)["modules"]]
        assert paths == sorted(paths), f"modules not sorted by path: {paths}"

        # A config naming one root must not drop the others. The config that
        # setup itself writes was the first victim: on a backend/ + frontend/
        # repo it collapsed detection to one module over the whole tree.
        cfg = tmp / ".codedna"
        cfg.mkdir()
        (cfg / "config.json").write_text('{"mode":"auto","moduleRoots":["services"]}')
        narrowed = {m["path"] for m in detect(tmp)["modules"]}
        assert "packages/util" in narrowed, f"config replaced defaults instead of extending: {narrowed}"

        # Every extension counted as source must map to a language, or the
        # module reports language "unknown".
        from detect_modules import EXT_LANG, SOURCE_EXT

        assert not set(SOURCE_EXT) - set(EXT_LANG), sorted(set(SOURCE_EXT) - set(EXT_LANG))

        # ids name exactly one module: services/auth and packages/auth collided.
        ids = [m["id"] for m in detect(tmp)["modules"]]
        assert len(ids) == len(set(ids)), f"duplicate module ids: {ids}"

        # A subsystem spanning directories: declared, not detected, and it gets
        # a path-scoped rule because no single directory contains it.
        span = Path(tempfile.mkdtemp())
        try:
            (span / "inc/abilities").mkdir(parents=True)
            (span / "assets/js/core").mkdir(parents=True)
            (span / ".codedna").mkdir()
            (span / "inc/abilities/loader.php").write_text("<?php\n")
            (span / "assets/js/core/bridge.js").write_text("//\n")
            (span / ".codedna/config.json").write_text(json.dumps({"modules": [
                "inc/abilities",
                {"id": "ability-bridge", "paths": ["inc/abilities/**", "assets/js/core/**"]},
            ]}))
            mods = {m["id"]: m for m in detect(span)["modules"]}
            assert "ability-bridge" in mods, mods
            bridge = mods["ability-bridge"]
            assert bridge["rule"] == ".claude/rules/ability-bridge.md", bridge
            assert "path" not in bridge, "a seam has no single directory"
            assert mods["abilities"]["path"] == "inc/abilities", mods["abilities"]
        finally:
            shutil.rmtree(span, ignore_errors=True)

        # No root matched at all: the whole repo is a guess, so setup must ask.
        solo = Path(tempfile.mkdtemp())
        try:
            (solo / "main.py").write_text("x = 1\n")
            (solo / "util.py").write_text("y = 2\n")
            mods = detect(solo)["modules"]
            assert mods and mods[0]["path"] == ".", mods
            assert mods[0]["confidence"] == "low", mods[0]
            assert mods[0]["reason"] == "whole-repo-fallback", mods[0]
        finally:
            shutil.rmtree(solo, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"detection ok ({len(found)} modules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
