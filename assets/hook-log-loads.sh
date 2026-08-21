#!/usr/bin/env bash
# InstructionsLoaded hook: record which docs actually reached a session.
#
# The whole design rests on Claude Code auto-loading a module's CLAUDE.md when
# it reads a file in that directory, and path-scoped rules when a glob matches.
# Nothing told you whether that happened. If it silently stopped — a moved path,
# a claudeMdExcludes entry, a rule whose globs match nothing — you would read
# the docs as not helping, when the truth is they never arrived.
#
# Appends one JSON line per load to .codedna/.load-log. `measure` reports it.
#
# Install: copy to .claude/hooks/log-loads.sh, chmod +x, merge
# assets/hook-example.json into .claude/settings.json. Requires jq.
# Add .codedna/.load-log to .gitignore — it is machine-local, not shared.
set -uo pipefail

command -v jq >/dev/null 2>&1 || exit 0   # no jq: log nothing rather than break loading

input=$(cat)
root="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -d "$root/.codedna" ] || exit 0

# The event's field names are not pinned in the docs, so rather than guess one,
# walk the payload for anything that looks like a markdown path. Robust to the
# schema changing, and the paths are the part that matters.
jq -c --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  {
    ts: $ts,
    reason: (.reason // .matcher // .source // .hook_event_name // "unknown"),
    files: ([.. | strings | select(test("\\.md$"))] | unique)
  } | select(.files | length > 0)
' <<<"$input" >> "$root/.codedna/.load-log" 2>/dev/null

exit 0
