"""
SpamAssassin pilot rule discovery.

This module performs a lightweight static discovery pass over SpamAssassin
rule files inside the running SpamAssassin container.

Purpose
-------
The goal of this helper is not to evaluate emails directly, but to identify
candidate rules that may be relevant for the manual rule-based pilot. In
particular, it looks for rules that are defined on lexical surfaces such as
the subject or body and therefore may be potentially affected by zero-width
Unicode salting (e.g. U+200B).

Workflow
--------
1. Locate SpamAssassin rule files inside the container.
2. Read and parse rule definitions from .cf / .pre files.
3. Extract rule metadata such as:
   - rule name
   - rule type
   - expression
   - score
   - description
   - source file and line number
4. Apply simple heuristics to classify:
   - the rule surface (subject / body / other)
   - the expected breakability via U+200B salting
5. Write the discovered candidates to CSV and JSON.

Notes
-----
- This is a discovery utility for pilot preparation, not a full semantic
  parser of SpamAssassin rules.
- The breakability classification is heuristic only and serves as a first
  filter for manual inspection.
- Container output is decoded as UTF-8 with replacement to avoid Windows
  host decoding issues when reading rule files through docker exec.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

from config import BASE_DIR, SPAMASSASSIN_CONTAINER
from src.utils.console import print_end, print_kv, print_section, print_step


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/sa/rule_discovery"


RULE_START_RE = re.compile(
    r"^(header|body|rawbody|full|uri)\s+([A-Z0-9_]+)\s+(.*)$"
)
DESCRIBE_RE = re.compile(r"^describe\s+([A-Z0-9_]+)\s+(.*)$")
SCORE_RE = re.compile(r"^score\s+([A-Z0-9_]+)\s+(.+)$")


def _run_in_container(command: str) -> str:
    """
    Execute a shell command inside the SpamAssassin container and return stdout.

    The command output is decoded as UTF-8 with replacement in order to avoid
    host-side decoding failures on Windows systems when docker returns bytes
    that are not compatible with the local default code page.

    Args:
        command: Shell command to execute inside the container.

    Returns:
        Decoded stdout as a string.
    """
    result = subprocess.run(
        ["docker", "exec", SPAMASSASSIN_CONTAINER, "sh", "-lc", command],
        check=True,
        capture_output=True,
        text=False,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _find_rule_files() -> list[str]:
    """
    Discover SpamAssassin rule files inside common container paths.

    The function scans multiple typical SpamAssassin directories to avoid
    hardcoding a single path assumption. It returns both .cf and .pre files,
    although the downstream parsing mainly targets rule-like configuration
    lines relevant for candidate discovery.

    Returns:
        Sorted list of matching rule file paths inside the container.
    """
    cmd = r"""
dirs="
/var/lib/spamassassin
/usr/share/spamassassin
/etc/mail/spamassassin
"
for d in $dirs; do
  if [ -d "$d" ]; then
    find "$d" -type f \( -name "*.cf" -o -name "*.pre" \) 2>/dev/null
  fi
done | sort -u
"""
    output = _run_in_container(cmd)
    files = [
        line.strip()
        for line in output.splitlines()
        if line.strip().endswith((".cf", ".pre"))
    ]
    return files


def _read_rule_file(container_path: str) -> str:
    """
    Read a rule file from inside the SpamAssassin container.

    Args:
        container_path: Absolute path to the file inside the container.

    Returns:
        File content as a decoded string.
    """
    cmd = f'cat "{container_path}"'
    return _run_in_container(cmd)


def _classify_surface(rule_type: str, expression: str) -> str:
    """
    Classify the primary lexical surface addressed by a rule.

    This is a coarse heuristic used to group candidate rules into:
    - subject: header rules explicitly referencing the subject
    - body: body-like rules
    - other: everything else

    Args:
        rule_type: SpamAssassin rule type (e.g. header, body, rawbody).
        expression: Rule expression as parsed from the rule file.

    Returns:
        One of: "subject", "body", "other".
    """
    expr = expression.lower()

    # Header rules that explicitly reference the subject are treated as
    # subject-facing candidates.
    if rule_type == "header":
        if "subject" in expr:
            return "subject"
        return "other"

    # Body-related rule types are grouped as body-facing candidates.
    if rule_type in {"body", "rawbody", "full", "uri"}:
        return "body"

    return "other"


def _classify_breakability(rule_type: str, expression: str) -> str:
    """
    Estimate whether a rule may be breakable via U+200B salting.

    The classification is intentionally heuristic. It does not prove actual
    bypassability, but highlights lexical candidates that are more promising
    for manual pilot testing.

    Heuristic logic:
    - clearly structural / metadata-oriented rules -> unlikely
    - body-like rules -> likely
    - subject-referencing header rules -> likely
    - lexical-looking expressions with token-oriented hints -> likely
    - otherwise -> unknown

    Args:
        rule_type: SpamAssassin rule type.
        expression: Rule expression as parsed from the rule file.

    Returns:
        One of: "likely", "unlikely", "unknown".
    """
    expr = expression.lower()

    # Hints suggesting a lexical / token-oriented rule that could plausibly be
    # affected when visible words are fragmented by zero-width characters.
    lexical_hints = [
        "subject",
        "body",
        "rawbody",
        r"\b",
        "[a-z",
        "[A-Z",
        "[a-zA-Z",
        "verify",
        "family",
        "seen",
        "account",
        "password",
        "click",
        "secure",
    ]

    # Hints suggesting a structural, MIME, transport, or metadata rule that is
    # less likely to be affected by lexical salting in the visible text.
    structural_hints = [
        "all_caps",
        "charset",
        "mime",
        "base64",
        "html_",
        "message-id",
        "date",
        "from:",
        "to:",
        "received",
    ]

    if any(h in expr for h in structural_hints):
        return "unlikely"

    if rule_type in {"body", "rawbody", "full", "uri"}:
        return "likely"

    if rule_type == "header" and "subject" in expr:
        return "likely"

    if any(h in expression for h in lexical_hints):
        return "likely"

    return "unknown"


def _parse_rule_files(rule_files: list[str]) -> list[dict]:
    """
    Parse discovered rule files and build a flat candidate list.

    For each file, the parser extracts:
    - rule definition lines
    - description lines
    - score lines

    It then merges these fragments by rule name, applies the surface and
    breakability heuristics, and returns a list of candidate rows suitable
    for CSV/JSON export.

    Args:
        rule_files: List of rule file paths inside the container.

    Returns:
        List of candidate rule dictionaries.
    """
    rules: dict[str, dict] = {}

    for file_path in rule_files:
        try:
            content = _read_rule_file(file_path) or ""
        except subprocess.CalledProcessError as exc:
            print_kv("skip_file", file_path)
            print_kv("reason", f"docker exec failed: {exc}")
            continue
        except Exception as exc:
            print_kv("skip_file", file_path)
            print_kv("reason", f"unexpected read error: {exc}")
            continue

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            m = RULE_START_RE.match(line)
            if m:
                rule_type, rule_name, expression = m.groups()
                rules.setdefault(rule_name, {})
                rules[rule_name].update(
                    {
                        "rule_name": rule_name,
                        "rule_type": rule_type,
                        "expression": expression.strip(),
                        "defined_in": file_path,
                        "defined_at_line": line_number,
                    }
                )
                continue

            m = DESCRIBE_RE.match(line)
            if m:
                rule_name, description = m.groups()
                rules.setdefault(rule_name, {})
                rules[rule_name]["description"] = description.strip()
                continue

            m = SCORE_RE.match(line)
            if m:
                rule_name, score = m.groups()
                rules.setdefault(rule_name, {})
                rules[rule_name]["score"] = score.strip()
                continue

    rows: list[dict] = []

    for rule_name, data in sorted(rules.items()):
        rule_type = data.get("rule_type", "")
        expression = data.get("expression", "")

        # Limit the output to rule types that are relevant for this pilot
        # discovery step.
        if rule_type not in {"header", "body", "rawbody", "full", "uri"}:
            continue

        surface = _classify_surface(rule_type, expression)
        breakability = _classify_breakability(rule_type, expression)

        rows.append(
            {
                "rule_name": rule_name,
                "rule_type": rule_type,
                "surface": surface,
                "breakability_u200b": breakability,
                "score": data.get("score", ""),
                "description": data.get("description", ""),
                "expression": expression,
                "defined_in": data.get("defined_in", ""),
                "defined_at_line": data.get("defined_at_line", ""),
            }
        )

    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    """
    Write discovered candidate rows to a semicolon-separated CSV file.

    Args:
        path: Target CSV path.
        rows: Candidate rows to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return

        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict) -> None:
    """
    Write discovery metadata to a JSON file.

    Args:
        path: Target JSON path.
        data: JSON-serializable metadata dictionary.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_sa_rule_discovery() -> None:
    """
    Run the SpamAssassin pilot rule discovery step.

    This function orchestrates the static discovery workflow:
    - find rule files in the container
    - parse and classify candidate rules
    - export candidate data to CSV and JSON
    - print a short console summary

    Output files:
        - sa_rule_candidates.csv
        - sa_rule_candidates.json
    """
    print_step("SA Pilot - Rule Discovery")

    rule_files = _find_rule_files()
    rows = _parse_rule_files(rule_files)

    csv_path = OUTPUT_ROOT / "sa_rule_candidates.csv"
    json_path = OUTPUT_ROOT / "sa_rule_candidates.json"

    _write_csv(csv_path, rows)
    _write_json(
        json_path,
        {
            "rule_file_count": len(rule_files),
            "candidate_count": len(rows),
            "rule_files": rule_files,
        },
    )

    subject_count = sum(1 for r in rows if r["surface"] == "subject")
    body_count = sum(1 for r in rows if r["surface"] == "body")
    likely_count = sum(1 for r in rows if r["breakability_u200b"] == "likely")

    print_section("Discovery summary")
    print_kv("rule_files", len(rule_files))
    print_kv("candidates", len(rows))
    print_kv("subject_candidates", subject_count)
    print_kv("body_candidates", body_count)
    print_kv("likely_breakable", likely_count)
    print_kv("csv", csv_path)
    print_kv("json", json_path)
    print_end("SA Pilot - Rule Discovery")


if __name__ == "__main__":
    run_sa_rule_discovery()