#!/usr/bin/env python3
"""
Evaluates the effect of zero-width Unicode salting on the Rspamd neural pilot case.

The unsalted pilot message is scanned as the baseline. A salted variant is
generated from the case body and compared with respect to the overall score,
neural score, and resulting classification.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from config import (
    PILOT_RS_NEURAL_OUTPUT_DIR,
    PILOT_RS_NEURAL_FROM_ADDR,
    PILOT_RS_NEURAL_TO_ADDR,
    PILOT_RS_NEURAL_SALT_MODE,
    PILOT_RS_NEURAL_INSERT_AFTER_INDEX,
)
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_scan
from src.pilot.rspamd.neural_based.cases import NEURAL_CASES, CODEPOINT_CHAR, CODEPOINT_NAME
from src.pilot.rspamd.neural_based.template_builder_neural import create_paired_bytes, write_message
from src.utils.console import print_step, print_section, print_kv, print_end


OUTPUT_ROOT = PILOT_RS_NEURAL_OUTPUT_DIR
TEST_UNSALTED_DIR = OUTPUT_ROOT / "messages" / "unsalted"
TEST_SALTED_DIR = OUTPUT_ROOT / "messages" / "salted"
RESULTS_DIR = OUTPUT_ROOT / "results"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text or "")


def _unique_tokens(text: str) -> list[str]:
    tokens = [token for token in _tokenize_text(text) if len(token) >= 4]
    return list(dict.fromkeys(tokens))


def _scan_summary(email_path: Path) -> dict:
    scan = run_rspamd_scan(email_path)
    return {
        "spam_flag": scan["spam_flag"],
        "score": scan["score"],
        "threshold": scan["threshold"],
        "action": scan["action"],
        "rules": scan["rules"],
        "has_neural": scan["has_neural"],
        "neural_symbol": scan["neural_symbol"],
        "neural_score": scan["neural_score"],
        "raw_output": scan["raw_output"],
    }


def _extract_neural_details(raw_output) -> dict:
    """
    Extract detailed NEURAL_SPAM information from the raw Rspamd response.

    Args:
        raw_output: Raw Rspamd response as a dictionary or JSON string.

    Returns:
        dict: Neural score, description, and options if available.
    """

    if not raw_output:
        return {}

    if isinstance(raw_output, str):
        try:
            raw_output = json.loads(raw_output)
        except Exception:
            return {}

    if not isinstance(raw_output, dict):
        return {}

    symbols = raw_output.get("symbols", {})
    neural = symbols.get("NEURAL_SPAM")

    if not isinstance(neural, dict):
        return {}

    return {
        "score": neural.get("score"),
        "description": neural.get("description"),
        "options": neural.get("options"),
    }


def _delta(a, b):
    if a is None or b is None:
        return None
    return b - a


def run_rspamd_pilot_neural_eval() -> None:
    print_step("Rspamd Pilot - Neural Eval")

    case = NEURAL_CASES[0]
    unsalted_path = TEST_UNSALTED_DIR / f"{case.case_id}_unsalted.eml"

    if not unsalted_path.exists():
        raise FileNotFoundError(
            f"Unsalted pilot mail not found: {unsalted_path}. "
            f"Run run_rspamd_pilot_neural_prepare() first."
        )

    print_section("Pilot case")
    print_kv("case_id", case.case_id)
    print_kv("title", case.title)

    subject_tokens: list[str] = []

    # Salt all unique body tokens of at least four characters.
    body_tokens = _unique_tokens(case.body)

    print_section("Salting targets")
    print_kv("subject_tokens", subject_tokens)
    print_kv("body_tokens", body_tokens)
    print_kv("salt_mode", PILOT_RS_NEURAL_SALT_MODE)
    print_kv("insert_after_index", PILOT_RS_NEURAL_INSERT_AFTER_INDEX)

    print_section("Baseline scan")
    baseline = _scan_summary(unsalted_path)
    baseline_neural_details = _extract_neural_details(baseline["raw_output"])

    print_section("Baseline neural details")
    print_kv("neural_options", baseline_neural_details.get("options"))
    print_kv("neural_description", baseline_neural_details.get("description"))
    print_kv("score", baseline["score"])
    print_kv("action", baseline["action"])
    print_kv("has_neural", baseline["has_neural"])
    print_kv("neural_symbol", baseline["neural_symbol"])
    print_kv("neural_score", baseline["neural_score"])

    salted_path = TEST_SALTED_DIR / f"{case.case_id}_salted_all_tokens.eml"

    _, salted_bytes, counts = create_paired_bytes(
        subject=case.subject,
        body=case.body,
        target_tokens_subject=tuple(subject_tokens),
        target_tokens_body=tuple(body_tokens),
        codepoint=CODEPOINT_CHAR,
        from_addr=PILOT_RS_NEURAL_FROM_ADDR,
        to_addr=PILOT_RS_NEURAL_TO_ADDR,
    )
    write_message(salted_path, salted_bytes)

    print_section("Salted scan")
    salted = _scan_summary(salted_path)
    salted_neural_details = _extract_neural_details(salted["raw_output"])

    print_section("Salted neural details")
    print_kv("neural_options", salted_neural_details.get("options"))
    print_kv("neural_description", salted_neural_details.get("description"))
    print_kv("score", salted["score"])
    print_kv("action", salted["action"])
    print_kv("has_neural", salted["has_neural"])
    print_kv("neural_symbol", salted["neural_symbol"])
    print_kv("neural_score", salted["neural_score"])

    results_csv = RESULTS_DIR / "rspamd_pilot_neural_results.csv"
    results_json = RESULTS_DIR / "rspamd_pilot_neural_summary.json"
    manifest_json = RESULTS_DIR / f"{case.case_id}_salting_manifest.json"

    rows = [
        {
            "case_id": case.case_id,
            "variant": "unsalted",
            "score": baseline["score"],
            "threshold": baseline["threshold"],
            "action": baseline["action"],
            "spam_flag": baseline["spam_flag"],
            "has_neural": baseline["has_neural"],
            "neural_symbol": baseline["neural_symbol"],
            "neural_score": baseline["neural_score"],
            "n_insert_subject": 0,
            "n_insert_body": 0,
            "target_tokens_subject": "",
            "target_tokens_body": "",
            "message_path": str(unsalted_path),
        },
        {
            "case_id": case.case_id,
            "variant": "salted",
            "score": salted["score"],
            "threshold": salted["threshold"],
            "action": salted["action"],
            "spam_flag": salted["spam_flag"],
            "has_neural": salted["has_neural"],
            "neural_symbol": salted["neural_symbol"],
            "neural_score": salted["neural_score"],
            "n_insert_subject": counts["n_insert_subject"],
            "n_insert_body": counts["n_insert_body"],
            "target_tokens_subject": "|".join(subject_tokens),
            "target_tokens_body": "|".join(body_tokens),
            "message_path": str(salted_path),
        },
    ]
    _write_csv(results_csv, rows)

    summary = {
        "case_id": case.case_id,
        "title": case.title,
        "salt_mode": PILOT_RS_NEURAL_SALT_MODE,
        "insert_after_index": PILOT_RS_NEURAL_INSERT_AFTER_INDEX,
        "selected_tokens_subject": subject_tokens,
        "selected_tokens_body": body_tokens,
        "unsalted_score": baseline["score"],
        "salted_score": salted["score"],
        "delta_score": _delta(baseline["score"], salted["score"]),
        "unsalted_neural_symbol": baseline["neural_symbol"],
        "salted_neural_symbol": salted["neural_symbol"],
        "unsalted_neural_score": baseline["neural_score"],
        "salted_neural_score": salted["neural_score"],
        "delta_neural_score": _delta(baseline["neural_score"], salted["neural_score"]),
        "unsalted_action": baseline["action"],
        "salted_action": salted["action"],
        "unsalted_spam_flag": baseline["spam_flag"],
        "salted_spam_flag": salted["spam_flag"],
    }
    _write_json(results_json, summary)

    manifest = {
        "case_id": case.case_id,
        "codepoint": CODEPOINT_NAME,
        "target_tokens_subject": subject_tokens,
        "target_tokens_body": body_tokens,
        "salt_mode": PILOT_RS_NEURAL_SALT_MODE,
        "insert_after_index": PILOT_RS_NEURAL_INSERT_AFTER_INDEX,
        "n_insert_subject": counts["n_insert_subject"],
        "n_insert_body": counts["n_insert_body"],
    }
    _write_json(manifest_json, manifest)

    print_section("Comparison")
    print_kv("delta_score", _delta(baseline["score"], salted["score"]))
    print_kv("delta_neural_score", _delta(baseline["neural_score"], salted["neural_score"]))
    print_kv("spam_flag_unsalted", baseline["spam_flag"])
    print_kv("spam_flag_salted", salted["spam_flag"])

    print_section("Output files")
    print_kv("results_csv", results_csv)
    print_kv("results_json", results_json)
    print_kv("manifest_json", manifest_json)

    print_end("Rspamd Pilot - Neural Eval")


if __name__ == "__main__":
    run_rspamd_pilot_neural_eval()