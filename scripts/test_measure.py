#!/usr/bin/env python3
"""Payload-counter self-check: python3 scripts/test_measure.py

The counter decides whether a doc is reported as OVERHEAD — delete. Calling a
good doc empty is the worst thing this tool can do, so both shapes people
actually write (bullets and prose) have to count, and everything that only
looks like content must not.
"""

import re

from measure import PAYLOAD_SECTIONS, items_under

PROSE = """## Rules

This module must never import the mailer. It emits a PaymentSettled event
and notifications subscribes to it.

## Gotchas

The Stripe webhook regularly arrives before our own transaction commits.
"""

BULLETS = """## Rules

- never imports the mailer
- amounts are integer minor units

## Gotchas

- webhook can arrive before our commit lands
"""

UNFILLED = """## Rules

<!-- Things that are true and must stay true. Write the rule, not the state. -->

- {{INVARIANTS}}

## Gotchas

## Why it is this way

- UNKNOWN
"""

DERIVABLE_ONLY = """## Responsibility

- handles payments

## Important files

- pay.py
- refund.py
"""


def main() -> int:
    # prose counts: one item per block, not one per wrapped line
    assert items_under(PROSE, PAYLOAD_SECTIONS) == 2, items_under(PROSE, PAYLOAD_SECTIONS)
    assert items_under(BULLETS, PAYLOAD_SECTIONS) == 3, items_under(BULLETS, PAYLOAD_SECTIONS)

    # a scaffolded-but-unwritten doc carries nothing: placeholders, a bare
    # UNKNOWN bullet, an empty section, and guidance inside HTML comments
    assert items_under(UNFILLED, PAYLOAD_SECTIONS) == 0, items_under(UNFILLED, PAYLOAD_SECTIONS)

    # sections holding only derivable facts are not payload
    assert items_under(DERIVABLE_ONLY, PAYLOAD_SECTIONS) == 0

    # the shipped template must read as empty, or every fresh scaffold looks full
    from pathlib import Path

    assets = Path(__file__).parent.parent / "assets"
    tmpl = (assets / "architecture.md").read_text()
    assert items_under(tmpl, PAYLOAD_SECTIONS) == 0, "template counts as payload"

    module_tmpl = (assets / "module-CLAUDE.md").read_text()
    assert items_under(module_tmpl, PAYLOAD_SECTIONS) == 0, "module template counts as payload"

    # The split has to stay unambiguous: rules and gotchas are stated where they
    # auto-load, rationale where it is read on demand. A section appearing in
    # both files is the ambiguity that makes people write to neither.
    def sections(text):
        return {
            line.lstrip("#").strip().lower()
            for line in re.sub(r"<!--.*?-->", "", text, flags=re.S).splitlines()
            if line.startswith("##")
        }

    overlap = sections(tmpl) & sections(module_tmpl)
    assert not overlap, f"sections in both templates: {overlap}"
    assert {"rules", "gotchas"} <= sections(module_tmpl), sections(module_tmpl)
    assert "why it is this way" in sections(tmpl), sections(tmpl)

    # No hand-written timestamp: git records when a file changed, a written
    # date does not, and it conflicts on every concurrent edit.
    assert "last_updated" not in tmpl.split("<!--")[0], "timestamp back in the template"

    # A fresh scaffold must read as "nothing to say yet", not as a pile of open
    # questions. UNKNOWN is counted as a question someone owes an answer to.
    for name in ("architecture.md", "module-CLAUDE.md"):
        body = re.sub(r"<!--.*?-->", "", (assets / name).read_text(), flags=re.S)
        assert "UNKNOWN" not in body, f"{name} scaffolds an open question"

    # setup runs more than once, by more than one person. The markers are what
    # make a second run replace the block instead of appending a duplicate.
    root_tmpl = (assets / "root-CLAUDE.md").read_text()
    for marker in ("<!-- codedna:start", "<!-- codedna:end"):
        assert marker in root_tmpl, f"missing {marker} in root template"

    # A hedge is not content. It used to count as payload and as an open
    # question at the same time.
    assert items_under("## Rules\n\n- UNKNOWN: ask Dave\n", PAYLOAD_SECTIONS) == 0
    assert items_under("## Rules\n\n- never import the mailer\n", PAYLOAD_SECTIONS) == 1

    # "we do not know" and "it never loaded" must not read the same
    import json as _json
    import shutil as _shutil
    import tempfile as _tempfile
    from measure import loads_per_doc

    tmp = Path(_tempfile.mkdtemp())
    try:
        (tmp / ".codedna").mkdir()
        assert loads_per_doc(tmp) is None, "no log must be unknown, not zero"
        (tmp / ".codedna/.load-log").write_text(
            _json.dumps({"ts": "t", "reason": "nested_traversal",
                         "files": ["a/CLAUDE.md"]}) + "\n"
            + "not json at all\n"
            + _json.dumps({"ts": "t", "reason": "path_glob_match",
                           "files": ["a/CLAUDE.md", "b/rule.md"]}) + "\n"
        )
        counts = loads_per_doc(tmp)
        assert counts == {"a/CLAUDE.md": 2, "b/rule.md": 1}, counts
    finally:
        _shutil.rmtree(tmp, ignore_errors=True)

    print("payload counter ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
