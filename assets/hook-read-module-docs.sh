#!/usr/bin/env bash
# PreToolUse hook: before Claude edits a file, inject that module's
# architecture.md. Nested CLAUDE.md files already load on their own; this covers
# architecture.md, which does not, and it fires whether or not the model decided
# to read anything.
#
# Resolves the module from .codedna/modules.json by longest matching path, NOT
# by walking up the directory tree. Walking up meant a file in a nested package
# got its ancestor's architecture.md injected, labelled as if it were its own —
# confidently wrong context, which is the failure this tool exists to prevent.
#
# Install: copy to .claude/hooks/read-module-docs.sh, chmod +x, and merge
# assets/hook-example.json into .claude/settings.json. Requires jq.
#
# Optional. Most repos are fine relying on the auto-loaded module CLAUDE.md
# pointing at architecture.md.
set -uo pipefail

command -v jq >/dev/null 2>&1 || exit 0   # no jq: do nothing rather than break every edit

input=$(cat)
path=$(jq -r '.tool_input.file_path // empty' <<<"$input") || exit 0
[ -n "$path" ] || exit 0

root="${CLAUDE_PROJECT_DIR:-$PWD}"
modules="$root/.codedna/modules.json"
[ -f "$modules" ] || exit 0

rel="${path#"$root"/}"
[ "$rel" != "$path" ] || exit 0          # edit outside the project: not ours

# Only architecture.md. A module's CLAUDE.md and a subsystem's path-scoped rule
# both auto-load already — injecting them here would duplicate context the
# harness has supplied, which is the waste this tool exists to avoid.
# Longest matching module path wins, so a nested package never inherits its
# parent's doc.
arch=$(jq -r --arg rel "$rel" '
  [ .modules[] | . as $m
    | select($m.path != null and ($rel == $m.path or ($rel | startswith($m.path + "/"))))
    | select($m.architecture != null)
  ] | sort_by(.path | length) | last | .architecture // empty
' "$modules") || exit 0
[ -n "$arch" ] && [ -f "$root/$arch" ] || exit 0

jq -n --arg p "$arch" --arg c "$(cat "$root/$arch")" \
  '{hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: ("Module context from " + $p + ":\n\n" + $c)
    }}'
