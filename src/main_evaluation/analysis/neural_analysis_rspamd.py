#!/usr/bin/env python3
"""
Analyzes Rspamd neural behavior for baseline-detected spam emails.

The analysis compares neural symbol presence and scores between baseline messages
and their salted variants, including symbol loss and aggregated score changes.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.utils.console import print_step, print_section, print_kv, print_end


def _read_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _to_float(value):
    if value in (None, "", "None"):
        return None
    return float(value)


def run_neural_analysis_rspamd(
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
):
    """
    Analyze Rspamd neural behavior for baseline-detected spam and salted variants.

    Args:
        results_csv (Path): Variant-level evaluation results.
        paired_csv (Path): Paired baseline and salted evaluation results.
        output_dir (Path): Directory for analysis artifacts.

    Returns:
        dict: Aggregated neural presence, loss, symbol, and score statistics.
    """

    results_rows = _read_csv(results_csv)
    paired_rows = _read_csv(paired_csv)

    baseline_detected_ids = {
        row["message_id"]
        for row in paired_rows
        if _to_bool(row.get("baseline_spam_flag"))
    }

    baseline_rows = [
        row for row in results_rows
        if row.get("dataset") == "baseline"
        and row.get("label") == "spam"
        and row.get("message_id") in baseline_detected_ids
    ]

    salted_rows = [
        row for row in results_rows
        if row.get("dataset") == "salted"
        and row.get("label") == "spam"
        and row.get("message_id") in baseline_detected_ids
    ]

    n_baseline_detected_emails = len(baseline_rows)
    baseline_with_neural_rows = [
        row for row in baseline_rows
        if _to_bool(row.get("has_neural"))
    ]
    n_baseline_with_neural = len(baseline_with_neural_rows)

    baseline_neural_symbol_counts = Counter(
        row.get("neural_symbol", "")
        for row in baseline_with_neural_rows
        if row.get("neural_symbol")
    )

    baseline_neural_scores = [
        _to_float(row.get("neural_score"))
        for row in baseline_with_neural_rows
        if _to_float(row.get("neural_score")) is not None
    ]

    salted_rows_by_message = defaultdict(list)
    for row in salted_rows:
        salted_rows_by_message[row["message_id"]].append(row)

    n_salted_with_any_neural = 0
    n_neural_lost_any = 0
    n_neural_lost_all = 0

    salted_neural_symbol_counts = Counter()
    salted_neural_score_values = []

    for message_id in baseline_detected_ids:
        variants = salted_rows_by_message.get(message_id, [])
        if not variants:
            continue

        has_any_neural = any(_to_bool(v.get("has_neural")) for v in variants)
        has_all_neural = all(_to_bool(v.get("has_neural")) for v in variants)

        if has_any_neural:
            n_salted_with_any_neural += 1

        if not has_all_neural:
            n_neural_lost_any += 1

        if not has_any_neural:
            n_neural_lost_all += 1

        for variant in variants:
            if _to_bool(variant.get("has_neural")) and variant.get("neural_symbol"):
                salted_neural_symbol_counts[variant["neural_symbol"]] += 1

            neural_score = _to_float(variant.get("neural_score"))
            if neural_score is not None:
                salted_neural_score_values.append(neural_score)

    summary = {
        "n_baseline_detected_emails": n_baseline_detected_emails,
        "n_baseline_with_neural": n_baseline_with_neural,
        "n_salted_with_any_neural": n_salted_with_any_neural,
        "n_neural_lost_any": n_neural_lost_any,
        "n_neural_lost_all": n_neural_lost_all,
        "baseline_neural_symbol_counts": dict(sorted(baseline_neural_symbol_counts.items())),
        "salted_neural_symbol_counts": dict(sorted(salted_neural_symbol_counts.items())),
        "baseline_neural_score_mean": (
            round(sum(baseline_neural_scores) / len(baseline_neural_scores), 6)
            if baseline_neural_scores else None
        ),
        "salted_neural_score_mean": (
            round(sum(salted_neural_score_values) / len(salted_neural_score_values), 6)
            if salted_neural_score_values else None
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "neural_analysis_rspamd.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print_step("Neural Analysis (Rspamd)")
    print_section("Output files")
    print_kv("neural_analysis_rspamd_json", output_path)
    print_end("Neural Analysis (Rspamd)")

    return summary