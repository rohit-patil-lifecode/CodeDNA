#!/usr/bin/env python3
"""Is CodeDNA earning its context? Cost vs payload, per module.

    python3 scripts/measure.py --root .

Cost is what these files add to a session. Payload is what they carry that
Claude could not read off the code. A module whose doc costs tokens and carries
no boundaries, gotchas, or rationale is overhead — delete it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

# Sections carrying what the code cannot state: rules and gotchas in CLAUDE.md,
# rationale in architecture.md.
PAYLOAD_SECTIONS = ("rules", "gotchas", "why it is this way")
# A line that starts with UNKNOWN/TBD is a hedge, not content. Anchored to
# the whole line before, so "UNKNOWN: ask Dave" counted as payload and as an
# open question simultaneously.
PLACEHOLDER = re.compile(r"\{\{.*?\}\}|^(UNKNOWN|TBD)\b", re.I)
SKIP_RE = re.compile(r"codedna:\s*skip-docs", re.I)


def tokens(text: str) -> int:
    """Rough but consistent: ~4 bytes per token."""
    return len(text.encode("utf-8")) // 4


def items_under(text: str, wanted: tuple[str, ...]) -> int:
    """Count content items under the named section(s).

    A bullet is one item; a run of prose lines is one item. People write a
    gotcha as a sentence at least as often as a bullet, and calling a good
    prose doc empty would be the exact mistake this tool exists to catch.
    Template guidance lives in HTML comments and is stripped first.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    count, active, in_prose = 0, False, False
    for line in text.splitlines():
        if line.startswith("#"):
            active, in_prose = line.lstrip("#").strip().lower() in wanted, False
            continue
        if not active:
            continue
        stripped = line.strip()
        if not stripped:
            in_prose = False
            continue
        if stripped.startswith(("-", "*")):
            in_prose = False
            body = stripped.lstrip("-* ").strip()  # strip marker before the check
            if body and not PLACEHOLDER.search(body):
                count += 1
        elif PLACEHOLDER.search(stripped):
            in_prose = False
        elif not in_prose:  # first line of a prose block
            in_prose = True
            count += 1
    return count


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def loads_per_doc(root: Path) -> dict[str, int] | None:
    """How many times each doc actually reached a session.

    None means no log — the InstructionsLoaded hook is not installed, so we
    genuinely do not know, which is different from knowing it never loaded.
    """
    log = root / ".codedna" / ".load-log"
    if not log.exists():
        return None
    counts: dict[str, int] = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            for doc in json.loads(line).get("files") or []:
                counts[doc] = counts.get(doc, 0) + 1
        except json.JSONDecodeError:
            continue
    return counts


def load_modules(root: Path) -> list[dict]:
    path = root / ".codedna" / "modules.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("modules") or []


def empty_doc_edits(root: Path, limit: int) -> int:
    """Commits that touched a doc without adding content — the cheat rate.

    Watches both doc names. Watching only architecture.md meant a content-free
    touch to CLAUDE.md — the file that auto-loads, and the one people edit to
    clear a gate — never showed up here.
    """
    log = git(root, "log", f"-{limit}", "--format=%H")
    if not log:
        return 0
    hits = 0
    for sha in log.splitlines():
        diff = git(
            root, "show", "--unified=0", "--format=", sha,
            "--", "*architecture.md", "*CLAUDE.md",
        )
        if not diff.strip():
            continue
        real = [
            line
            for line in diff.splitlines()
            if line.startswith(("+", "-"))
            and not line.startswith(("+++", "---"))
            and line[1:].strip()
        ]
        if not real:
            hits += 1
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure CodeDNA cost vs payload")
    parser.add_argument("--root", default=".")
    parser.add_argument("--history", type=int, default=50, help="commits to scan")
    parser.add_argument("--json", action="store_true", help="emit as JSON for trend tracking")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    modules = load_modules(root)
    if not modules:
        print("No .codedna/modules.json. Run `/codedna setup` first.")
        return 1

    root_md = next((root / n for n in ("CLAUDE.md", ".claude/CLAUDE.md") if (root / n).exists()), None)
    always_on = tokens(read(root_md)) if root_md else 0

    rows, overhead = [], []
    total_cost = total_payload = 0
    for mod in modules:
        # a subsystem rule auto-loads on any matching path, so it is auto cost
        claude = root / (mod.get("rule") or mod.get("claude", ""))
        arch = root / mod.get("architecture", "") if mod.get("architecture") else root / ""
        if not claude.exists() and not arch.exists():
            continue
        c_text, a_text = read(claude), read(arch)
        auto, on_demand = tokens(c_text), tokens(a_text)
        payload = items_under(a_text, PAYLOAD_SECTIONS) + items_under(c_text, PAYLOAD_SECTIONS)
        rows.append((mod["id"], auto, on_demand, payload, mod.get("path") or mod["id"]))
        total_cost += auto + on_demand
        total_payload += payload
        if payload == 0:
            overhead.append(mod["architecture"])

    unknowns = sum(
        read(root / m[k]).count("UNKNOWN")
        for m in modules
        for k in ("claude", "architecture", "rule")
        if m.get(k)
    )
    cheats = empty_doc_edits(root, args.history)
    skips = len(SKIP_RE.findall(git(root, "log", f"-{args.history}", "--format=%B")))

    if args.json:
        print(json.dumps({
            "alwaysOnTokens": always_on,
            "totalCost": total_cost,
            "totalPayload": total_payload,
            "zeroPayload": overhead,
            "modules": [
                {"id": r[0], "path": r[4], "autoLoad": r[1], "onDemand": r[2], "payload": r[3]}
                for r in rows
            ],
            "trust": {"unknowns": unknowns, "contentFreeDocEdits": cheats, "skipDocsCommits": skips},
            "loads": loads_per_doc(root),
        }, indent=2))
        return 0

    print("CodeDNA / measure\n")
    print(f"{'module':<28}{'auto-load':>10}{'on-demand':>11}{'payload':>9}  verdict")
    for mid, auto, dem, payload, path in sorted(rows, key=lambda r: r[3]):
        cost = auto + dem
        verdict = "OVERHEAD — delete" if payload == 0 else f"{cost // payload} tok/item"
        print(f"{path[:27]:<28}{auto:>10}{dem:>11}{payload:>9}  {verdict}")

    print(f"\nAlways-on (root CLAUDE.md): {always_on} tok")
    print(f"Per module touched:         {total_cost // max(len(rows), 1)} tok average")
    print(f"Payload carried:            {total_payload} items code cannot tell you")
    if overhead:
        print(f"\nZero-payload docs ({len(overhead)}) — cost with nothing to show for it:")
        for path in overhead:
            print(f"  - {path}")

    seen = loads_per_doc(root)
    print("\nReaching Claude")
    if seen is None:
        print("  unknown — no .codedna/.load-log.")
        print("  Install the InstructionsLoaded hook (assets/hook-log-loads.sh) to")
        print("  find out whether these docs load at all. Without it, a doc that")
        print("  never arrives is indistinguishable from a doc that did not help.")
    else:
        docs = [d for m in modules for k in ("claude", "architecture", "rule")
                if (d := m.get(k)) and (root / d).exists()]
        never = [d for d in docs if not seen.get(d)]
        loaded = sorted(((seen.get(d, 0), d) for d in docs if seen.get(d)), reverse=True)
        for count, doc in loaded[:5]:
            print(f"  {count:>4}x  {doc}")
        if never:
            print(f"  never loaded ({len(never)}): {', '.join(never[:4])}")
            print("  ^ written, but no session has seen them. Check the path, the")
            print("    globs, and claudeMdExcludes before concluding docs do not help.")

    print("\nTrust signals")
    print(f"  UNKNOWN fields still open:            {unknowns}")
    print(f"  content-free doc edits (last {args.history}):     {cheats}")
    print(f"  skip-docs commits (last {args.history}):          {skips}")
    if cheats or skips:
        print("  ^ docs are being satisfied, not written. Investigate before enforcing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
