from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

from config import BASE_DIR, RSPAMD_CONTAINER
from src.utils.console import print_end, print_kv, print_section, print_step


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/rspamd/rule_discovery"
RSPAMD_RULES_DIR = "/usr/share/rspamd/rules"
RSPAMD_REGEXP_DIR = "/usr/share/rspamd/rules/regexp"


def _run_in_container(command: str) -> str:
    result = subprocess.run(
        ["docker", "exec", RSPAMD_CONTAINER, "sh", "-lc", command],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _subject_regexp_symbols() -> tuple[list[str], str]:
    cmd = r'''
rspamadm configdump regexp \
| awk '
  /^[A-Z0-9_]+[[:space:]]*\{/ {sym=$1}
  /Subject=\// || /raw_header_exists\(Subject\)/ || /header_exists\(Subject\)/ {print sym}
' \
| sort -u
'''
    raw = _run_in_container(cmd)
    symbols = [line.strip() for line in raw.splitlines() if line.strip()]
    return symbols, raw


def _subject_lua_hits() -> tuple[list[dict], str]:
    cmd = rf"grep -RInE 'get_header\\(|\\bSubject\\b|\\bsubject\\b' {RSPAMD_RULES_DIR} || true"
    raw = _run_in_container(cmd)
    hits: list[dict] = []
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        file_path, line_no, content = parts
        hits.append(
            {
                "file": file_path.strip(),
                "line": int(line_no),
                "content": content.strip(),
            }
        )
    return hits, raw


def _body_selector_hits() -> tuple[list[dict], str]:
    cmd = rf"grep -RInE '\\{{sa_body\\}}|\\{{words\\}}' {RSPAMD_REGEXP_DIR} | sed 's|{RSPAMD_REGEXP_DIR}/||' || true"
    raw = _run_in_container(cmd)
    hits: list[dict] = []
    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        rel_file, line_no, content = parts
        selector = "sa_body" if "{sa_body}" in content else "words" if "{words}" in content else ""
        hits.append(
            {
                "file": rel_file.strip(),
                "line": int(line_no),
                "selector": selector,
                "content": content.strip(),
            }
        )
    return hits, raw


def _safe_cat(container_path: str) -> str:
    try:
        return _run_in_container(f'cat "{container_path}"')
    except subprocess.CalledProcessError:
        return ""


def _extract_misc_targets(misc_text: str) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(misc_text.splitlines(), start=1):
        s = line.strip()
        if "{sa_body}" in s:
            rows.append(
                {
                    "selector": "sa_body",
                    "source_file": "misc.lua",
                    "line": line_no,
                    "symbol_or_target": "INTRODUCTION",
                    "target_hint": "my name is / i am / this is + title",
                    "pattern": s,
                    "used_in_manual_pilot": True,
                }
            )
        elif "webcam" in s and "{words}" in s:
            rows.append(
                {
                    "selector": "words",
                    "source_file": "misc.lua",
                    "line": line_no,
                    "symbol_or_target": "LEAKED_PASSWORD_SCAM",
                    "target_hint": "webcam",
                    "pattern": s,
                    "used_in_manual_pilot": True,
                }
            )
        elif re.search(r"pass(?:word|phrase)", s, flags=re.I) and "{words}" in s:
            rows.append(
                {
                    "selector": "words",
                    "source_file": "misc.lua",
                    "line": line_no,
                    "symbol_or_target": "LEAKED_PASSWORD_SCAM",
                    "target_hint": "password / passphrase",
                    "pattern": s,
                    "used_in_manual_pilot": False,
                }
            )
        elif "wallet" in s and "{words}" in s:
            rows.append(
                {
                    "selector": "words",
                    "source_file": "misc.lua",
                    "line": line_no,
                    "symbol_or_target": "LEAKED_PASSWORD_SCAM",
                    "target_hint": "wallet",
                    "pattern": s,
                    "used_in_manual_pilot": False,
                }
            )
    return rows


def _manual_subject_rows(subject_symbols: list[str]) -> list[dict]:
    selected = [
        ("SUBJ_BOUNCE_WORDS", "Keyword- / phrase-based bounce detection", True),
        ("SUBJ_ALL_CAPS", "Mostly uppercase subject", True),
        ("LONG_SUBJ", "Long UTF-8 subject", True),
        ("SUBJECT_HAS_EXCLAIM", "Subject contains exclamation mark", True),
        ("SUBJECT_HAS_QUESTION", "Subject contains question mark", True),
        ("SUBJECT_ENDS_SPACES", "Subject ends with whitespace", True),
        ("SUBJECT_ENDS_EXCLAIM", "Subject ends with exclamation mark", True),
        ("SUBJECT_NEEDS_ENCODING", "Non-ASCII subject requires RFC 2047 encoding", False),
    ]
    available = set(subject_symbols)
    rows: list[dict] = []
    for symbol, rationale, used in selected:
        rows.append(
            {
                "surface": "subject",
                "symbol": symbol,
                "source": "manual_pilot_subject_selection",
                "discovered_via": "rspamadm configdump regexp + grep subject Lua",
                "present_in_regexp_discovery": symbol in available,
                "used_in_manual_pilot": used,
                "selection_rationale": rationale,
            }
        )
    return rows


def _manual_body_rows(misc_targets: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in misc_targets:
        rows.append(
            {
                "surface": "body",
                "symbol": item["symbol_or_target"],
                "selector": item["selector"],
                "source": item["source_file"],
                "line": item["line"],
                "target_hint": item["target_hint"],
                "pattern": item["pattern"],
                "used_in_manual_pilot": item["used_in_manual_pilot"],
                "discovered_via": "grep -RInE {sa_body}|{words} /usr/share/rspamd/rules/regexp",
            }
        )
    return rows


def run_rspamd_rule_discovery() -> None:
    print_step("Rspamd rule discovery")

    subject_symbols, subject_regexp_raw = _subject_regexp_symbols()
    subject_lua_hits, subject_lua_raw = _subject_lua_hits()
    body_hits, body_hits_raw = _body_selector_hits()

    subject_checks_lua = _safe_cat(f"{RSPAMD_RULES_DIR}/subject_checks.lua")
    bounce_lua = _safe_cat(f"{RSPAMD_RULES_DIR}/bounce.lua")
    misc_lua = _safe_cat(f"{RSPAMD_RULES_DIR}/regexp/misc.lua")

    misc_targets = _extract_misc_targets(misc_lua)
    subject_rows = _manual_subject_rows(subject_symbols)
    body_rows = _manual_body_rows(misc_targets)

    combined_rows: list[dict] = []
    for row in subject_rows:
        combined_rows.append(row)
    for row in body_rows:
        combined_rows.append(row)

    csv_path = OUTPUT_ROOT / "rspamd_rule_candidates_manual.csv"
    summary_path = OUTPUT_ROOT / "rspamd_rule_discovery_summary.json"

    _write_csv(csv_path, combined_rows)
    _write_json(
        summary_path,
        {
            "subject_regexp_symbols": subject_symbols,
            "subject_regexp_symbol_count": len(subject_symbols),
            "subject_lua_hit_count": len(subject_lua_hits),
            "body_selector_hit_count": len(body_hits),
            "manual_subject_rule_count": len(subject_rows),
            "manual_body_target_count": len(body_rows),
            "csv": str(csv_path),
            "artifacts": {
                "subject_regexp_symbols_txt": str(OUTPUT_ROOT / "subject_regexp_symbols.txt"),
                "subject_lua_hits_txt": str(OUTPUT_ROOT / "subject_lua_hits.txt"),
                "body_selector_hits_txt": str(OUTPUT_ROOT / "body_selector_hits.txt"),
                "subject_checks_lua_txt": str(OUTPUT_ROOT / "subject_checks.lua.txt"),
                "bounce_lua_txt": str(OUTPUT_ROOT / "bounce.lua.txt"),
                "misc_lua_txt": str(OUTPUT_ROOT / "misc.lua.txt"),
            },
        },
    )

    _write_text(OUTPUT_ROOT / "subject_regexp_symbols.txt", subject_regexp_raw)
    _write_text(OUTPUT_ROOT / "subject_lua_hits.txt", subject_lua_raw)
    _write_text(OUTPUT_ROOT / "body_selector_hits.txt", body_hits_raw)
    _write_text(OUTPUT_ROOT / "subject_checks.lua.txt", subject_checks_lua)
    _write_text(OUTPUT_ROOT / "bounce.lua.txt", bounce_lua)
    _write_text(OUTPUT_ROOT / "misc.lua.txt", misc_lua)

    print_section("Discovery summary")
    print_kv("subject_regexp_symbols", len(subject_symbols))
    print_kv("subject_lua_hits", len(subject_lua_hits))
    print_kv("body_selector_hits", len(body_hits))
    print_kv("manual_subject_rules", len(subject_rows))
    print_kv("manual_body_targets", len(body_rows))
    print_kv("csv", csv_path)
    print_kv("json", summary_path)
    print_end("Rspamd rule discovery")


if __name__ == "__main__":
    run_rspamd_rule_discovery()
