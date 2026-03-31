"""
SpamAssassin pilot rule selection.

This module performs a filtering and prioritization step on the rule
candidates discovered in the rule discovery phase.

Purpose
-------
The goal is to reduce the large set of discovered SpamAssassin rules to a
manageable subset of high-quality candidates for the manual rule-based pilot.

The selection focuses on rules that:
- operate on lexical surfaces (subject or body)
- are likely breakable via U+200B salting
- do not belong to structural or metadata-based categories (e.g. MIME, DKIM)

Workflow
--------
1. Load candidate rules from the discovery CSV.
2. Apply filtering criteria to remove:
   - structural rules (headers, encoding, transport)
   - non-lexical rules
   - rules unlikely to be affected by salting
3. Split remaining candidates into:
   - subject-based rules
   - body-based rules
4. Rank candidates using a simple priority heuristic:
   - lexical relevance (keywords like "verify", "password", ...)
   - presence of description
   - absolute rule score
5. Export top-N candidates (top 50 each) for manual inspection.

Notes
-----
- This is a heuristic pre-selection step for the pilot, not a formal rule analysis.
- The output is intended to guide manual test case construction.
- The ranking is deliberately simple and interpretable.
"""

from __future__ import annotations

import csv
from pathlib import Path

from config import BASE_DIR
from src.utils.console import print_end, print_kv, print_section, print_step


INPUT_CSV = BASE_DIR / "data/output/pilot/sa/rule_discovery/sa_rule_candidates.csv"
OUTPUT_ROOT = BASE_DIR / "data/output/pilot/sa/rule_selection"


EXCLUDE_NAME_HINTS = [
    "ALL_CAPS",
    "MIME",
    "CHARSET",
    "BASE64",
    "HTML",
    "DATE",
    "FROM",
    "TO",
    "SUBJECT_NEEDS_ENCODING",
    "MESSAGE_ID",
    "RCVD",
    "DNS",
    "DKIM",
    "SPF",
    "DMARC",
    "HELO",
    "RDNS",
]

EXCLUDE_EXPR_HINTS = [
    "all_caps",
    "charset",
    "mime",
    "base64",
    "html",
    "message-id",
    "received",
    "dkim",
    "spf",
    "dmarc",
    "date",
    "from:",
    "to:",
]

INCLUDE_LEXICAL_HINTS = [
    r"\b",
    "subject =~",
    "body ",
    "rawbody ",
    "full ",
    "uri ",
    "verify",
    "account",
    "password",
    "family",
    "secure",
    "click",
    "seen",
]


def _read_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: str) -> float | None:
    try:
        return float(str(value).split()[0])
    except Exception:
        return None


def _contains_any(text: str, hints: list[str]) -> bool:
    text_lower = text.lower()
    return any(h.lower() in text_lower for h in hints)


def _is_candidate(row: dict) -> bool:
    rule_name = str(row.get("rule_name", ""))
    expression = str(row.get("expression", ""))
    surface = str(row.get("surface", ""))
    breakability = str(row.get("breakability_u200b", ""))

    if surface not in {"subject", "body"}:
        return False

    if breakability != "likely":
        return False

    if _contains_any(rule_name, EXCLUDE_NAME_HINTS):
        return False

    if _contains_any(expression, EXCLUDE_EXPR_HINTS):
        return False

    if not _contains_any(expression, INCLUDE_LEXICAL_HINTS):
        return False

    return True


def _priority_score(row: dict) -> tuple:
    score = _to_float(str(row.get("score", "")))
    abs_score = abs(score) if score is not None else 0.0

    description = str(row.get("description", ""))
    expression = str(row.get("expression", ""))

    lexical_bonus = 1 if _contains_any(expression, ["verify", "account", "password", "family", "secure", "seen"]) else 0
    has_description = 1 if description else 0

    return (
        lexical_bonus,
        has_description,
        abs_score,
        row.get("rule_name", ""),
    )


def run_sa_rule_selection() -> None:
    print_step("SA Pilot - Rule Selection")

    rows = _read_csv(INPUT_CSV)
    candidates = [row for row in rows if _is_candidate(row)]

    subject_rows = [row for row in candidates if row["surface"] == "subject"]
    body_rows = [row for row in candidates if row["surface"] == "body"]

    subject_rows = sorted(subject_rows, key=_priority_score, reverse=True)
    body_rows = sorted(body_rows, key=_priority_score, reverse=True)

    subject_top = subject_rows[:50]
    body_top = body_rows[:50]

    _write_csv(OUTPUT_ROOT / "sa_subject_candidates_top50.csv", subject_top)
    _write_csv(OUTPUT_ROOT / "sa_body_candidates_top50.csv", body_top)

    print_section("Selection summary")
    print_kv("all_candidates", len(candidates))
    print_kv("subject_top50", len(subject_top))
    print_kv("body_top50", len(body_top))
    print_kv("subject_csv", OUTPUT_ROOT / "sa_subject_candidates_top50.csv")
    print_kv("body_csv", OUTPUT_ROOT / "sa_body_candidates_top50.csv")
    print_end("SA Pilot - Rule Selection")


if __name__ == "__main__":
    run_sa_rule_selection()