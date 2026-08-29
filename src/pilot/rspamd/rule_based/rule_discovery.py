"""
Discovers content-related Rspamd rules for the rule-based pilot study.

Regexp and Lua rule files are inspected inside the Rspamd container and
classified according to the message representation they operate on.
The discovered rules are deduplicated and exported for pilot case selection.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import List, Dict

from config import PILOT_RS_RULE_DISCOVERY_OUTPUT_DIR, RSPAMD_CONTAINER
from src.utils.console import print_step, print_section, print_kv, print_end


OUTPUT_ROOT = PILOT_RS_RULE_DISCOVERY_OUTPUT_DIR
RSPAMD_RULES_DIR = "/usr/share/rspamd/rules"
RSPAMD_REGEXP_DIR = "/usr/share/rspamd/rules/regexp"


# ============================================================
# Container helper
# ============================================================

def _run(cmd: str) -> str:
    """
    Execute a shell command inside the Rspamd container.

    Args:
        cmd (str): Shell command to execute.

    Returns:
        str: Standard output produced by the command.
    """

    result = subprocess.run(
        ["docker", "exec", RSPAMD_CONTAINER, "sh", "-lc", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# ============================================================
# Rule-Type classification
# ============================================================

def classify_rule(selector: str, content: str) -> str:
    """
    Map a Rspamd selector to the corresponding rule category.

    Args:
        selector (str): Selector extracted from the rule definition.
        content (str): Raw rule definition.

    Returns:
        str: Classified rule category.
    """

    content_lower = content.lower()

    if selector == "words":
        return "body_words"

    if selector == "raw_words":
        return "body_raw_words"

    if selector == "sa_body":
        return "body_sa_body"

    if selector == "sa_raw_body":
        return "body_raw"

    if selector == "header":
        return "header"

    if selector == "raw_header":
        return "raw_header"

    if selector == "mime":
        return "mime"

    if selector == "raw_mime":
        return "raw_mime"

    # Treat simple Boolean combinations as composite rules when no selector matched.
    if " and " in content_lower or " or " in content_lower:
        return "composite"

    return "unknown"


# ============================================================
# REGEXP RULE DISCOVERY
# ============================================================

def discover_regexp_rules() -> List[Dict]:
    """
    Discover selector-based rules in Rspamd regexp rule files.

    Returns:
        list[dict]: Discovered regexp rules and their classification metadata.
    """

    print_section("Regexp rule discovery")

    selectors = [
        "words",
        "raw_words",
        "sa_body",
        "sa_raw_body",
        "header",
        "raw_header",
        "mime",
        "raw_mime",
    ]

    # Search only for selectors relevant to content representations used by the pilot.
    grep_pattern = "|".join(rf"\{{{s}\}}" for s in selectors)

    cmd = rf"grep -RInE '{grep_pattern}' {RSPAMD_REGEXP_DIR} || true"
    raw = _run(cmd)

    rows = []

    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue

        file_path, line_no, content = parts

        selector = ""
        for s in selectors:
            if f"{{{s}}}" in content:
                selector = s
                break

        if not selector:
            continue

        rule_type = classify_rule(selector, content)

        rows.append(
            {
                "source": "regexp",
                "rule_type": rule_type,
                "selector": selector,
                "file": file_path.replace(RSPAMD_REGEXP_DIR + "/", ""),
                "line": int(line_no),
                "pattern": content.strip(),
            }
        )

    return rows


# ============================================================
# LUA RULE DISCOVERY
# ============================================================

def discover_lua_rules() -> List[Dict]:
    """
    Discover potentially relevant content-processing rules in Rspamd Lua files.

    Returns:
        list[dict]: Discovered Lua rules and their inferred classification metadata.
    """

    print_section("Lua rule discovery")

    cmd = rf"grep -RInE 'raw|mime|header|words|get_header' {RSPAMD_RULES_DIR} || true"
    raw = _run(cmd)

    rows = []

    for line in raw.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue

        file_path, line_no, content = parts
        content_lower = content.lower()

        # Infer the accessed message representation from keywords in the Lua source line.
        selector = "lua"
        rule_type = "lua"

        if "raw_header" in content_lower:
            selector = "raw_header"
            rule_type = "raw_header"

        elif "header" in content_lower:
            selector = "header"
            rule_type = "header"

        elif "raw_mime" in content_lower:
            selector = "raw_mime"
            rule_type = "raw_mime"

        elif "mime" in content_lower:
            selector = "mime"
            rule_type = "mime"

        elif "raw" in content_lower and "word" in content_lower:
            selector = "raw_words"
            rule_type = "body_raw_words"

        elif "word" in content_lower:
            selector = "words"
            rule_type = "body_words"

        rows.append(
            {
                "source": "lua",
                "rule_type": rule_type,
                "selector": selector,
                "file": file_path.replace(RSPAMD_RULES_DIR + "/", ""),
                "line": int(line_no),
                "pattern": content.strip(),
            }
        )

    return rows


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate(rows: List[Dict]) -> List[Dict]:
    """
    Remove duplicate discovered rules.

    Args:
        rows (list[dict]): Discovered rule records.

    Returns:
        list[dict]: Rules unique by category and pattern.
    """

    seen = set()
    unique = []

    for r in rows:
        # Rules with the same category and pattern are considered equivalent.
        key = (r["rule_type"], r["pattern"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    return unique


# ============================================================
# CSV EXPORT
# ============================================================

def write_csv(rows: List[Dict], path: Path) -> None:
    """
    Write discovered rule metadata to a semicolon-separated CSV file.

    Args:
        rows (list[dict]): Rule records to export.
        path (Path): Destination CSV path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rule_type",
        "selector",
        "source",
        "file",
        "line",
        "pattern",
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# SUMMARY
# ============================================================

def print_summary(rows: List[Dict]) -> None:
    """
    Print the number of discovered rules per rule category.

    Args:
        rows (list[dict]): Discovered rule records.
    """

    counts = {}

    for r in rows:
        counts[r["rule_type"]] = counts.get(r["rule_type"], 0) + 1

    print_section("Rule-Type Coverage")

    for k, v in sorted(counts.items()):
        print_kv(k, v)


# ============================================================
# MAIN
# ============================================================

def run_rspamd_rule_discovery() -> None:
    """
    Run rule discovery, deduplication, export, and summary generation.
    """

    print_step("Rspamd rule discovery (clean)")

    regexp_rows = discover_regexp_rules()
    lua_rows = discover_lua_rules()

    all_rows = regexp_rows + lua_rows
    unique_rows = deduplicate(all_rows)

    csv_path = OUTPUT_ROOT / "rspamd_rule_types_full.csv"
    write_csv(unique_rows, csv_path)

    print_summary(unique_rows)

    print_section("Output")
    print_kv("csv", csv_path)

    print_end("Rspamd rule discovery")


if __name__ == "__main__":
    run_rspamd_rule_discovery()