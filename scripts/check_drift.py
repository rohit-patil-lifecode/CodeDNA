#!/usr/bin/env python3
"""Report module docs that went stale: missing files, dead ADR links, or code
changed under a module while its docs stayed put.

Warns by default and exits 0. Pass --enforce to fail the build instead; do that
only once the module list is trusted, because a gate that blocks on day one
gets routed around and then it is permanently green and useless.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

DOC_NAMES = {"claude.md", "architecture.md"}
# Must start its own line and carry a reason. A bare substring match meant a PR
# template documenting the hatch — or a reviewer writing "don't use
# codedna: skip-docs here" — silently disabled the gate repo-wide, with CI
# still printing pass.
SKIP_RE = re.compile(r"^[ \t]*codedna:[ \t]*skip-docs\b[ \t]*[:\-—]?[ \t]*(?P<why>\S.*)$", re.I | re.M)

# Dependency manifests and lockfiles. Module docs no longer list dependencies
# (the code shows them), so a bump is not a knowledge change — and the bot that
# opens those PRs cannot write docs anyway.
NON_KNOWLEDGE = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "pyproject.toml",
    "composer.json",
    "requirements.txt",
}

NON_KNOWLEDGE_EXT = {".md", ".png", ".jpg", ".svg", ".map", ".snap"}

# Tests and generated code change constantly without moving a boundary.
NON_KNOWLEDGE_GLOBS = (
    "*_test.*", "*.test.*", "test_*.*", "*.spec.*", "*_spec.*",
    "*.pb.go", "*_pb2.py", "*_pb2_grpc.py", "*.pb.cc", "*.pb.h",
    "*.g.dart", "*.generated.*", "*_generated.*", "*.gen.go",
)
NON_KNOWLEDGE_DIRS = {"tests", "test", "__tests__", "spec", "testdata", "fixtures", "__mocks__"}

# Must stay equal to detect_modules.BUILD_DIRS — a folder that is never a module
# is never a knowledge change either. Kept as a literal, not an import, because
# CI fetches this file on its own. test_check_drift.py asserts they match.
DEFAULT_IGNORE = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "out",
    "coverage",
    "vendor",
    ".next",
    ".nuxt",
    "target",
    "__pycache__",
    "generated",
    "gen",
    ".venv",
    "bin",
    "obj",
    ".codedna",
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def load_config(root: Path) -> dict:
    path = root / ".codedna" / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_modules(root: Path, ignore: set[str]) -> tuple[list[dict], bool]:
    """Return (modules, from_manifest)."""
    path = root / ".codedna" / "modules.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data.get("modules") or []), True
    # Fallback for a repo that has docs but never committed modules.json.
    modules = []
    for arch in root.rglob("architecture.md"):
        rel_parts = arch.relative_to(root).parts
        if any(part in ignore for part in rel_parts):
            continue
        # a skill's own template directory is not a module
        if "assets" in rel_parts or ".claude" in rel_parts:
            continue
        folder = arch.parent
        modules.append(
            {
                "id": folder.name,
                "path": folder.relative_to(root).as_posix(),
                "claude": (folder / "CLAUDE.md").relative_to(root).as_posix(),
                "architecture": arch.relative_to(root).as_posix(),
            }
        )
    return modules, False


def diff_range(root: Path, base: str | None) -> str | None:
    """Git range to diff, or None for 'compare against the working tree'."""
    if not base:
        return None
    try:
        return f"{git(root, 'merge-base', base, 'HEAD')}..HEAD"
    except subprocess.CalledProcessError:
        return f"{base}..HEAD"


def changed_files(root: Path, rng: str | None) -> list[str]:
    try:
        if rng:
            return [f for f in git(root, "diff", "--name-only", rng).splitlines() if f]
        # plain paths, no porcelain status columns to slice off
        tracked = git(root, "diff", "--name-only", "HEAD")
        untracked = git(root, "ls-files", "--others", "--exclude-standard")
        return sorted({f for f in (tracked + "\n" + untracked).splitlines() if f})
    except subprocess.CalledProcessError as exc:
        print(f"git error: {exc}", file=sys.stderr)
        return []


def doc_edit_is_substantive(root: Path, rng: str | None, paths: list[str]) -> bool:
    """False when the docs changed by nothing but whitespace.

    The cheapest way to satisfy a docs gate is to touch the file without
    saying anything, so an edit that adds no content does not count. A
    brand-new doc file always counts.
    """
    for path in paths:
        if not (root / path).exists():
            continue
        try:
            diff = git(root, "diff", "--unified=0", rng or "HEAD", "--", path)
        except subprocess.CalledProcessError:
            return True
        if not diff.strip():  # untracked/new file: no diff to read, treat as real
            return True
        if any(
            line[1:].strip()
            for line in diff.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ):
            return True
    return False


def module_files(mod: dict, files: list[str]) -> list[str]:
    """Changed files belonging to this module — by directory, or by glob for a
    subsystem whose code spans directories."""
    if mod.get("paths"):
        return [f for f in files if any(fnmatch(f, pat) for pat in mod["paths"])]
    prefix = mod["path"].rstrip("/") + "/"
    return [f for f in files if f == mod["path"] or f.startswith(prefix)]


def module_docs(mod: dict) -> set[str]:
    """The docs that speak for this module, and only those."""
    if mod.get("rule"):
        return {mod["rule"]}
    return {mod.get("claude"), mod.get("architecture")} - {None}


def is_knowledge_file(path: str, ignore: set[str]) -> bool:
    p = Path(path)
    name = p.name.lower()
    if name in NON_KNOWLEDGE or name.endswith(".lock"):
        return False
    if p.suffix.lower() in NON_KNOWLEDGE_EXT and name not in DOC_NAMES:
        return False
    if any(fnmatch(name, pat) for pat in NON_KNOWLEDGE_GLOBS):
        return False
    parts = [part.lower() for part in p.parts]
    if any(part in NON_KNOWLEDGE_DIRS for part in parts[:-1]):
        return False
    return not any(part in ignore for part in p.parts)


def skip_requested(root: Path) -> bool:
    # On a PR the checked-out HEAD is often a synthetic merge commit whose
    # message nobody wrote, so also honour the marker from the environment
    # (wire CODEDNA_SKIP_DOCS to the PR title/body in CI).
    for text in (os.environ.get("CODEDNA_SKIP_DOCS", ""), _head_message(root)):
        match = SKIP_RE.search(text)
        if match:
            print(f"CodeDNA / check: skipped — {match.group('why').strip()}")
            return True
    return False


def _head_message(root: Path) -> str:
    try:
        return git(root, "log", "-1", "--pretty=%B")
    except subprocess.CalledProcessError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeDNA drift check")
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", default=None, help="git base ref, e.g. origin/main")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="exit 1 on findings instead of warning (default: warn, exit 0)",
    )
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    cfg = load_config(root)
    ignore = DEFAULT_IGNORE | set(cfg.get("ignore") or [])
    # manual mode means docs move when a human says so; never block that build
    enforce = args.enforce and cfg.get("mode", "auto") != "manual"

    issues: list[str] = []
    modules, from_manifest = load_modules(root, ignore)

    # never fail a repo that has not adopted CodeDNA yet
    skipped = not modules

    for mod in modules:
        if from_manifest and mod.get("path") and not (root / mod["path"]).exists():
            issues.append(
                f"module '{mod['id']}' is in modules.json but {mod['path']}/ is gone "
                f"— rerun detect_modules.py to prune it"
            )
            continue
        for doc in sorted(module_docs(mod)):
            if not (root / doc).exists():
                issues.append(f"missing {doc}")
        arch = root / mod.get("architecture", mod.get("rule", ""))
        if mod.get("architecture") and arch.exists():
            text = arch.read_text(encoding="utf-8", errors="replace")
            if "module:" not in text:
                issues.append(f"incomplete frontmatter {mod['architecture']}")
            for match in re.findall(r"docs/decisions/[\w./-]+", text):
                if not (root / match).exists():
                    issues.append(f"broken ADR link {match} in {mod['architecture']}")

    rng = diff_range(root, args.base)
    files = [] if skipped else changed_files(root, rng)
    if files and not skip_requested(root):
        for mod in modules:
            if mod.get("path") in {".", ""}:
                continue
            in_module = module_files(mod, files)
            own = module_docs(mod)
            code_changed = any(
                is_knowledge_file(f, ignore) and Path(f).name.lower() not in DOC_NAMES
                for f in in_module
            )
            touched_docs = [f for f in files if f in own]
            if not code_changed:
                continue
            if not touched_docs:
                issues.append(f"module '{mod['id']}' code changed, docs untouched")
            elif not doc_edit_is_substantive(root, rng, sorted(set(touched_docs))):
                issues.append(
                    f"module '{mod['id']}' docs touched but say nothing new"
                )

    status = "skipped" if skipped else ("fail" if enforce else "warn") if issues else "pass"
    if args.json:
        print(
            json.dumps(
                {
                    "status": status,
                    "modules": len(modules),
                    "changedFiles": len(files),
                    "findings": issues,
                },
                indent=2,
            )
        )
    else:
        print("CodeDNA / check")
        print(f"Modules: {len(modules)}")
        print(f"Changed files: {len(files)}")
        if skipped:
            print("Drift: skipped — no modules found. Run `/codedna setup` first.")
        elif issues:
            print(f"Drift: {status} ({len(issues)} findings)")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("Drift: pass")
    return 1 if issues and enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
