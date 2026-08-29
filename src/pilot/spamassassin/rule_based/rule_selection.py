"""
Selects lexical SpamAssassin rules for the rule-based pilot study.

Discovered candidates are filtered using heuristic inclusion and exclusion
criteria, ranked by relevance, and exported as separate subject and body
candidate lists for manual pilot case selection.
"""

from __future__ import annotations

import csv
from pathlib import Path

from config import BASE_DIR
from src.utils.console import print_end, print_kv, print_section, print_step


INPUT_CSV = BASE_DIR / "data/output/pilot/sa/rule_based/rule_discovery/sa_rule_candidates.csv"
OUTPUT_ROOT = BASE_DIR / "data/output/pilot/sa/rule_based/rule_selection"


# Exclude rule names associated primarily with structural or transport features.
EXCLUDE_NAME_HINTS = [
    "ALL_CAPS", "MIME", "CHARSET", "BASE64", "HTML", "DATE", "FROM", "TO",
    "SUBJECT_NEEDS_ENCODING", "MESSAGE_ID", "RCVD", "DNS", "DKIM", "SPF",
    "DMARC", "HELO", "RDNS",
]

# Apply equivalent exclusions to rule expressions.
EXCLUDE_EXPR_HINTS = [
    "all_caps", "charset", "mime", "base64", "html", "message-id",
    "received", "dkim", "spf", "dmarc", "date", "from:", "to:",
]

# Prefer expressions containing lexical patterns relevant to salting.
INCLUDE_LEXICAL_HINTS = [
    r"\b", "subject =~", "body ", "rawbody ", "full ", "uri ",
    "verify", "account", "password", "family", "secure", "click", "seen",
]


def _read_csv(path: Path) -> list[dict]:
    """
    Read rule candidates from a semicolon-delimited CSV file.

    Args:
        path (Path): Source CSV path.

    Returns:
        list[dict]: Candidate rule records.
    """

    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _write_csv(path: Path, rows: list[dict]) -> None:
    """
    Read rule candidates from a semicolon-delimited CSV file.

    Args:
        path (Path): Source CSV path.

    Returns:
        list[dict]: Candidate rule records.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: str) -> float | None:
    """
    Parse the first numeric value from a score field.

    Args:
        value (str): SpamAssassin score field.

    Returns:
        float | None: Parsed score, or None if conversion fails.
    """

    try:
        return float(str(value).split()[0])
    except Exception:
        return None


def _contains_any(text: str, hints: list[str]) -> bool:
    """
    Check whether text contains any configured hint.

    Args:
        text (str): Text to inspect.
        hints (list[str]): Candidate substrings.

    Returns:
        bool: True if at least one hint is present.
    """

    text_lower = text.lower()
    return any(h.lower() in text_lower for h in hints)


def _is_candidate(row: dict) -> bool:
    """
    Determine whether a discovered rule is suitable for lexical pilot selection.

    Args:
        row (dict): Discovered rule record.

    Returns:
        bool: True if the rule satisfies the selection heuristics.
    """

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
    """
    Build the ranking tuple used to prioritize lexical candidates.

    Args:
        row (dict): Candidate rule record.

    Returns:
        tuple: Ranking values used for descending candidate selection.
    """

    score = _to_float(str(row.get("score", "")))
    abs_score = abs(score) if score is not None else 0.0

    description = str(row.get("description", ""))
    expression = str(row.get("expression", ""))

    lexical_bonus = 1 if _contains_any(
        expression,
        ["verify", "account", "password", "family", "secure", "seen"],
    ) else 0
    has_description = 1 if description else 0

    # Prefer explicit lexical hints, available descriptions, and higher absolute scores.
    return (
        lexical_bonus,
        has_description,
        abs_score,
        row.get("rule_name", ""),
    )


def run_sa_rule_selection() -> None:
    """
    Filter, rank, and export the top subject and body rule candidates.
    """

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
