#!/usr/bin/env python3
"""Where the code shows a trap and the docs stay silent.

    python3 scripts/gaps.py --root . [--json]

Every workaround, retry and "do not remove" in a codebase is a bug somebody
already hit. If a module is full of them and its Gotchas section is empty, that
is not a simple module — it is an unwritten one, and the next person to touch it
pays the same afternoon again.

This counts the evidence and compares it to what the docs say. It does not read
meaning: a module with markers and no gotchas is a place to look, not a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Each of these exists because someone lost time to it.
MARKERS = [
    (re.compile(r"\b(HACK|FIXME|XXX|WORKAROUND)\b", re.I), "workaround marker"),
    (re.compile(r"(do ?n[o']?t\s+(remove|reorder|change|touch)|must\s+(run|be called|happen)\s+(before|after|first))", re.I), "ordering warning"),
    (re.compile(r"\bsetTimeout\s*\([^,]+,\s*0\s*\)", re.I), "deferred to next tick"),
    (re.compile(r"\b(retry|retries|backoff|attempts?\s*[<>=+])\b", re.I), "retry"),
    (re.compile(r"\b(race condition|deadlock|flaky|intermittent)\b", re.I), "race noted in a comment"),
    (re.compile(r"\b(sleep|usleep|time\.sleep)\s*\(", re.I), "sleep"),
]

SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".go", ".py", ".rs", ".java", ".kt",
              ".php", ".cs", ".rb"}
SKIP = {"node_modules", ".git", "dist", "build", "vendor", "__pycache__", ".venv"}
GOTCHA_HEADING = re.compile(r"^#+\s*gotchas\s*$", re.I)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def sources(root: Path, mod: dict) -> list[Path]:
    from fnmatch import fnmatch

    if mod.get("paths"):
        return [p for p in root.rglob("*")
                if p.is_file() and p.suffix in SOURCE_EXT
                and not any(s in p.relative_to(root).parts for s in SKIP)
                and any(fnmatch(p.relative_to(root).as_posix(), g) for g in mod["paths"])]
    base = root / mod.get("path", "")
    if not base.is_dir():
        return []
    return [p for p in base.rglob("*")
            if p.is_file() and p.suffix in SOURCE_EXT
            and not any(s in p.relative_to(base).parts for s in SKIP)]


def documented_gotchas(root: Path, mod: dict) -> int:
    """Content lines under a Gotchas heading, in whichever doc the module has."""
    count = 0
    for key in ("claude", "rule"):
        doc = mod.get(key)
        if not doc:
            continue
        text = re.sub(r"<!--.*?-->", "", read(root / doc), flags=re.S)
        active = False
        for line in text.splitlines():
            if line.startswith("#"):
                active = bool(GOTCHA_HEADING.match(line))
                continue
            body = line.strip().lstrip("-* ").strip()
            if active and body:
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Undocumented evidence per module")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    manifest = root / ".codedna" / "modules.json"
    if not manifest.exists():
        print("No .codedna/modules.json. Run `/codedna setup` first.")
        return 0
    modules = json.loads(read(manifest)).get("modules") or []

    report = []
    for mod in modules:
        hits: list[dict] = []
        for path in sources(root, mod):
            body = read(path)
            for lineno, line in enumerate(body.splitlines(), 1):
                for pattern, label in MARKERS:
                    if pattern.search(line):
                        hits.append({
                            "where": f"{path.relative_to(root).as_posix()}:{lineno}",
                            "kind": label,
                            "text": line.strip()[:100],
                        })
                        break
        if hits:
            report.append({
                "module": mod["id"],
                "evidence": len(hits),
                "documented": documented_gotchas(root, mod),
                "examples": hits[:5],
            })

    report.sort(key=lambda r: (r["documented"] == 0, r["evidence"]), reverse=True)
    unwritten = [r for r in report if r["documented"] == 0]

    if args.json:
        print(json.dumps({"modules": report, "unwritten": [r["module"] for r in unwritten]},
                         indent=2))
        return 0

    print("CodeDNA / gaps\n")
    if not report:
        print("No workarounds, retries or ordering warnings found in module code.")
        return 0
    for r in report:
        state = "nothing documented" if not r["documented"] else f"{r['documented']} documented"
        print(f"{r['module']}: {r['evidence']} traps in code, {state}")
        for ex in r["examples"]:
            print(f"    {ex['where']}  ({ex['kind']})  {ex['text']}")
        print()
    if unwritten:
        print(f"{len(unwritten)} module(s) carry evidence of past bugs and say nothing "
              f"about it: {', '.join(r['module'] for r in unwritten)}")
        print("Read the lines above and write what each one is protecting against.")
        print("These are the gotchas — the part that stops a plausible-looking fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
