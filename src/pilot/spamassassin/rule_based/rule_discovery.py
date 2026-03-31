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
    result = subprocess.run(
        ["docker", "exec", SPAMASSASSIN_CONTAINER, "sh", "-lc", command],
        check=True,
        capture_output=True,
        text=False,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _find_rule_files() -> list[str]:
    # Wir probieren mehrere typische Pfade, damit wir nicht blind einen einzigen hart verdrahten.
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
    cmd = f'cat "{container_path}"'
    return _run_in_container(cmd)


def _classify_surface(rule_type: str, expression: str) -> str:
    expr = expression.lower()

    # Subject-bezogene Header-Regeln
    if rule_type == "header":
        if "subject" in expr:
            return "subject"
        return "other"

    # Body-nahe Regeln
    if rule_type in {"body", "rawbody", "full", "uri"}:
        return "body"

    return "other"


def _classify_breakability(rule_type: str, expression: str) -> str:
    expr = expression.lower()

    # Grobe Heuristik für U+200B-breakbare, textgebundene Regeln
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
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        if not rows:
            f.write("")
            return

        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_sa_rule_discovery() -> None:
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