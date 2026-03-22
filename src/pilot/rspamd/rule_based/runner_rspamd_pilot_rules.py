#!/usr/bin/env python3
from __future__ import annotations

import csv
import time

import json
import subprocess
from pathlib import Path

from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd

from config import BASE_DIR, RSPAMD_CONTAINER
from src.pilot.rspamd.rule_based.cases import (
    RULE_CASES,
    CODEPOINT_NAME,
    CODEPOINT_CHAR,
)
from src.pilot.rspamd.rule_based.template_builder import (
    create_paired_bytes,
    write_message,
)
from src.utils.console import (
    print_end,
    print_kv,
    print_section,
    print_step,
)


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/rspamd/rules"


def _run_rspamc(email_path: Path) -> dict:
    with open(email_path, "rb") as f:
        result = subprocess.run(
            ["docker", "exec", "-i", RSPAMD_CONTAINER, "rspamc", "-j"],
            stdin=f,
            capture_output=True,
            text=True,
            check=True,
        )

    return json.loads(result.stdout)


def _extract_symbols(response: dict) -> list[str]:
    symbols = response.get("symbols", {})
    return list(symbols.keys())


def run_rspamd_pilot_rules() -> None:
    print_step("Rspamd Pilot - Rule Cases")

    activate_rspamd_config("rs_pilot_rules")
    restart_rspamd()
    time.sleep(5)

    print_step("Rspamd Pilot - Rule Cases")

    results_csv = OUTPUT_ROOT / "results" / "rspamd_pilot_rules_results.csv"
    summary_json = OUTPUT_ROOT / "results" / "rspamd_pilot_rules_summary.json"

    rows: list[dict] = []
    paired_summary: list[dict] = []

    for case in RULE_CASES:
        print_section(f"Case {case.case_id}")
        print_kv("title", case.title)
        print_kv("expected_rule", case.expected_rule)
        print_kv("expected_behavior", case.expected_behavior)

        unsalted_bytes, salted_bytes, counts = create_paired_bytes(
            subject=case.subject,
            body=case.body,
            target_tokens_subject=case.target_tokens_subject,
            target_tokens_body=case.target_tokens_body,
            codepoint=CODEPOINT_CHAR,
            from_addr="pilot@example.test",
            to_addr="victim@example.test",
        )

        unsalted_path = OUTPUT_ROOT / "messages" / "unsalted" / f"{case.case_id}_unsalted.eml"
        salted_path = OUTPUT_ROOT / "messages" / "salted" / f"{case.case_id}_salted.eml"

        write_message(unsalted_path, unsalted_bytes)
        write_message(salted_path, salted_bytes)

        unsalted_res = _run_rspamc(unsalted_path)
        salted_res = _run_rspamc(salted_path)

        unsalted_symbols = _extract_symbols(unsalted_res)
        salted_symbols = _extract_symbols(salted_res)

        unsalted_hit = case.expected_rule in unsalted_symbols
        salted_hit = case.expected_rule in salted_symbols

        break_success = unsalted_hit and not salted_hit

        if case.expected_behavior == "preserve":
            case_success = unsalted_hit and salted_hit
        else:
            case_success = break_success

        rows.extend(
            [
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "variant": "unsalted",
                    "expected_rule": case.expected_rule,
                    "expected_behavior": case.expected_behavior,
                    "symbols": "|".join(unsalted_symbols),
                    "expected_rule_hit": unsalted_hit,
                    "n_insert_subject": 0,
                    "n_insert_body": 0,
                    "codepoint": "",
                    "message_path": str(unsalted_path),
                    "case_success": case_success,
                },
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "variant": "salted",
                    "expected_rule": case.expected_rule,
                    "expected_behavior": case.expected_behavior,
                    "symbols": "|".join(salted_symbols),
                    "expected_rule_hit": salted_hit,
                    "n_insert_subject": counts["n_insert_subject"],
                    "n_insert_body": counts["n_insert_body"],
                    "codepoint": CODEPOINT_NAME,
                    "message_path": str(salted_path),
                    "case_success": case_success,
                },
            ]
        )

        paired_summary.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "expected_rule": case.expected_rule,
                "expected_behavior": case.expected_behavior,
                "codepoint": CODEPOINT_NAME,
                "n_insert_subject": counts["n_insert_subject"],
                "n_insert_body": counts["n_insert_body"],
                "unsalted_hit": unsalted_hit,
                "salted_hit": salted_hit,
                "break_success": break_success,
                "case_success": case_success,
                "unsalted_symbols": unsalted_symbols,
                "salted_symbols": salted_symbols,
                "unsalted_message_path": str(unsalted_path),
                "salted_message_path": str(salted_path),
            }
        )

        print_section("Unsalted")
        print_kv("hit", unsalted_hit)
        print_kv("symbols", "|".join(unsalted_symbols))

        print_section("Salted")
        print_kv("codepoint", CODEPOINT_NAME)
        print_kv("n_insert_subject", counts["n_insert_subject"])
        print_kv("n_insert_body", counts["n_insert_body"])
        print_kv("hit", salted_hit)
        print_kv("symbols", "|".join(salted_symbols))

        print_section("Result")
        print_kv("break_success", break_success)
        print_kv("case_success", case_success)

    results_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(results_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump({"paired_summary": paired_summary}, f, indent=2, ensure_ascii=False)

    print_section("Saved artifacts")
    print_kv("results_csv", results_csv)
    print_kv("summary_json", summary_json)
    print_end("Rspamd Pilot - Rule Cases")


if __name__ == "__main__":
    run_rspamd_pilot_rules()