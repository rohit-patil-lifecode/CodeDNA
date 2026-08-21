#!/usr/bin/env python3
"""Which modules change together — the architecture evidence git already holds.

    python3 scripts/coupling.py --root . [--since 200] [--json]

Modules that keep changing in the same commit are coupled, whatever the folder
structure says. That is evidence, not opinion, and it finds three things a code
read alone tends to miss:

  seam        two modules that almost always change together are one subsystem
              wearing two directory names. Declare it, or keep paying to
              rediscover the connection.
  hub         a module that changes alongside everything is where the design
              actually concentrates — and usually where nobody wrote the rules.
  orphan      a module nothing changes with. Either genuinely independent, or
              dead.

It reports; it does not judge. Whether a coupling is a problem depends on what
the project is for, which is a question for a human with the report in hand.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from fnmatch import fnmatch
from itertools import combinations
from pathlib import Path


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def owner_of(path: str, modules: list[dict]) -> str | None:
    """The module a changed file belongs to — longest directory match, or glob."""
    best, best_len = None, -1
    for mod in modules:
        if mod.get("paths"):
            if any(fnmatch(path, pat) for pat in mod["paths"]) and best_len < 0:
                best, best_len = mod["id"], 0
            continue
        mod_path = mod.get("path")
        if not mod_path or mod_path == ".":
            continue
        if path == mod_path or path.startswith(mod_path.rstrip("/") + "/"):
            if len(mod_path) > best_len:
                best, best_len = mod["id"], len(mod_path)
    return best


def commits_by_module(root: Path, modules: list[dict], since: int) -> list[set[str]]:
    """One set of module ids per commit that touched at least one module."""
    log = git(root, "log", f"-{since}", "--format=%x00%H", "--name-only")
    out, current = [], set()
    for line in log.splitlines():
        if line.startswith("\x00"):
            if current:
                out.append(current)
            current = set()
            continue
        if line.strip():
            mod = owner_of(line.strip(), modules)
            if mod:
                current.add(mod)
    if current:
        out.append(current)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Module coupling from git history")
    parser.add_argument("--root", default=".")
    parser.add_argument("--since", type=int, default=200, help="commits to read")
    parser.add_argument("--min-shared", type=int, default=3,
                        help="ignore pairs seen together fewer times than this")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    manifest = root / ".codedna" / "modules.json"
    if not manifest.exists():
        print("No .codedna/modules.json. Run `/codedna setup` first.")
        return 0
    modules = json.loads(manifest.read_text(encoding="utf-8")).get("modules") or []
    declared = {
        frozenset(m.get("members", [])) for m in modules if m.get("kind") == "subsystem"
    }

    history = commits_by_module(root, modules, args.since)
    if not history:
        print("No module changes in the last "
              f"{args.since} commits — nothing to infer from.")
        return 0

    churn = Counter(mid for commit in history for mid in commit)
    together: Counter[tuple[str, str]] = Counter()
    for commit in history:
        for pair in combinations(sorted(commit), 2):
            together[pair] += 1

    seams, hubs = [], []
    for (a, b), shared in together.most_common():
        if shared < args.min_shared:
            continue
        # of the times either changed, how often did they change as one unit
        union = churn[a] + churn[b] - shared
        strength = shared / union if union else 0
        if strength >= 0.5 and frozenset((a, b)) not in declared:
            seams.append({"modules": [a, b], "sharedCommits": shared,
                          "strength": round(strength, 2)})

    partners = Counter()
    for (a, b), shared in together.items():
        if shared >= args.min_shared:
            partners[a] += 1
            partners[b] += 1
    for mid, n in partners.most_common():
        if len(modules) > 3 and n >= max(3, (len(modules) - 1) * 0.6):
            hubs.append({"module": mid, "couplesWith": n, "commits": churn[mid]})

    orphans = [m["id"] for m in modules
               if churn[m["id"]] and partners[m["id"]] == 0]
    untouched = [m["id"] for m in modules if not churn[m["id"]]]

    if args.json:
        print(json.dumps({
            "commitsRead": len(history), "churn": dict(churn),
            "seams": seams, "hubs": hubs,
            "orphans": orphans, "untouched": untouched,
        }, indent=2))
        return 0

    print("CodeDNA / coupling")
    print(f"Commits read: {len(history)} touching {len(churn)} of {len(modules)} modules\n")

    if seams:
        print("Undeclared seams — these change as one unit, not two:")
        for s in seams:
            a, b = s["modules"]
            print(f"  {a} + {b}  — together in {s['sharedCommits']} commits "
                  f"({int(s['strength'] * 100)}% of the time either changed)")
        print("  Declare one in .codedna/config.json so its rules have a home.\n")
    if hubs:
        print("Hubs — change alongside most of the system:")
        for h in hubs:
            print(f"  {h['module']}  — couples with {h['couplesWith']} modules, "
                  f"{h['commits']} commits")
        print("  Concentration is not automatically wrong; undocumented "
              "concentration is.\n")
    if orphans:
        print(f"Independent — changed alone, never with another module: "
              f"{', '.join(orphans)}\n")
    if untouched:
        print(f"Untouched in this window: {', '.join(untouched)}\n")
    if not (seams or hubs):
        print("No strong coupling found. The module boundaries match how the "
              "code actually changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
