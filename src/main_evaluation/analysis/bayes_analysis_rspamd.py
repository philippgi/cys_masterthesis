#!/usr/bin/env python3
"""
Analyzes Rspamd Bayes behavior for baseline-detected spam emails.

The analysis compares Bayes symbol presence and scores between baseline messages
and their salted variants. Unlike SpamAssassin, Rspamd does not expose discrete
Bayes levels, so the analysis focuses on symbol loss and score changes.
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


def run_bayes_analysis_rspamd(
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
):
    """
    Analyze Rspamd Bayes behavior for baseline-detected spam and salted variants.

    Args:
        results_csv (Path): Variant-level evaluation results.
        paired_csv (Path): Paired baseline and salted evaluation results.
        output_dir (Path): Directory for analysis artifacts.

    Returns:
        dict: Aggregated Bayes presence, loss, symbol, and score statistics.
    """

    results_rows = _read_csv(results_csv)
    paired_rows = _read_csv(paired_csv)

    # -------------------------------------------------
    # Restrict analysis to baseline-detected spam emails
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Baseline stats
    # -------------------------------------------------
    n_baseline_detected_emails = len(baseline_rows)

    baseline_with_bayes_rows = [
        row for row in baseline_rows
        if _to_bool(row.get("has_bayes"))
    ]
    n_baseline_with_bayes = len(baseline_with_bayes_rows)

    baseline_bayes_symbol_counts = Counter(
        row.get("bayes_symbol", "")
        for row in baseline_with_bayes_rows
        if row.get("bayes_symbol")
    )

    baseline_bayes_scores = [
        _to_float(row.get("bayes_score"))
        for row in baseline_with_bayes_rows
        if _to_float(row.get("bayes_score")) is not None
    ]

    # -------------------------------------------------
    # Salted stats
    # -------------------------------------------------
    salted_rows_by_message = defaultdict(list)
    for row in salted_rows:
        salted_rows_by_message[row["message_id"]].append(row)

    n_salted_with_any_bayes = 0
    n_bayes_lost_any = 0
    n_bayes_lost_all = 0

    salted_bayes_symbol_counts = Counter()
    salted_bayes_score_values = []

    for message_id in baseline_detected_ids:
        variants = salted_rows_by_message.get(message_id, [])
        if not variants:
            continue

        has_any_bayes = any(_to_bool(v.get("has_bayes")) for v in variants)
        has_all_bayes = all(_to_bool(v.get("has_bayes")) for v in variants)

        if has_any_bayes:
            n_salted_with_any_bayes += 1

        # Lost in at least one variant
        if not has_all_bayes:
            n_bayes_lost_any += 1

        # Lost in all variants
        if not has_any_bayes:
            n_bayes_lost_all += 1

        for variant in variants:
            if _to_bool(variant.get("has_bayes")) and variant.get("bayes_symbol"):
                salted_bayes_symbol_counts[variant["bayes_symbol"]] += 1

            bayes_score = _to_float(variant.get("bayes_score"))
            if bayes_score is not None:
                salted_bayes_score_values.append(bayes_score)

    summary = {
        "n_baseline_detected_emails": n_baseline_detected_emails,
        "n_baseline_with_bayes": n_baseline_with_bayes,
        "n_salted_with_any_bayes": n_salted_with_any_bayes,
        "n_bayes_lost_any": n_bayes_lost_any,
        "n_bayes_lost_all": n_bayes_lost_all,
        "baseline_bayes_symbol_counts": dict(sorted(baseline_bayes_symbol_counts.items())),
        "salted_bayes_symbol_counts": dict(sorted(salted_bayes_symbol_counts.items())),
        "baseline_bayes_score_mean": (
            round(sum(baseline_bayes_scores) / len(baseline_bayes_scores), 6)
            if baseline_bayes_scores else None
        ),
        "salted_bayes_score_mean": (
            round(sum(salted_bayes_score_values) / len(salted_bayes_score_values), 6)
            if salted_bayes_score_values else None
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "bayes_analysis_rspamd.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print_step("Bayes Analysis (Rspamd)")

    print_section("Output files")
    print_kv("bayes_analysis_rspamd_json", output_path)

    print_end("Bayes Analysis (Rspamd)")

    return summary