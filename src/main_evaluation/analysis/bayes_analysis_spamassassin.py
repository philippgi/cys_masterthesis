#!/usr/bin/env python3
"""
Analyzes SpamAssassin Bayes behavior for baseline-detected spam emails.

The analysis compares discrete BAYES_* rule levels between baseline messages
and their salted variants, including level distributions, transitions, signal
loss, and aggregated Bayes scores.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.utils.console import print_step, print_section, print_kv, print_end


# Ordered from weakest to strongest Bayes evidence
BAYES_RULE_ORDER = [
    "BAYES_00",
    "BAYES_05",
    "BAYES_20",
    "BAYES_40",
    "BAYES_50",
    "BAYES_60",
    "BAYES_80",
    "BAYES_95",
    "BAYES_99",
    "BAYES_999",
]

BAYES_RULE_RANK = {rule: idx for idx, rule in enumerate(BAYES_RULE_ORDER)}

BAYES_RULE_SCORE = {
    "BAYES_00": 0.00,
    "BAYES_05": 0.05,
    "BAYES_20": 0.20,
    "BAYES_40": 0.40,
    "BAYES_50": 0.50,
    "BAYES_60": 0.60,
    "BAYES_80": 0.80,
    "BAYES_95": 0.95,
    "BAYES_99": 0.99,
    "BAYES_999": 0.999,
}

# --------------------------------------------------
# Utility
# --------------------------------------------------

def _parse_rules(rule_string: str) -> list[str]:
    """
    Parse a pipe-separated SpamAssassin rule string.

    Args:
        rule_string (str): Serialized rule list from the evaluation results.

    Returns:
        list[str]: Parsed rule names excluding empty and "none" entries.
    """

    if not rule_string:
        return []

    return [
        rule.strip()
        for rule in rule_string.split("|")
        if rule.strip() and rule.strip().lower() != "none"
    ]


def _extract_bayes_rules(rule_string: str) -> list[str]:
    """
    Extract Bayes-related rules from a serialized rule list.

    Args:
        rule_string (str): Serialized SpamAssassin rule list.

    Returns:
        list[str]: Rules beginning with BAYES_.
    """

    return [rule for rule in _parse_rules(rule_string) if rule.startswith("BAYES_")]


def _strongest_bayes_rule(bayes_rules: list[str]) -> str | None:
    """
    Select the strongest known Bayes rule from a rule list.

    Args:
        bayes_rules (list[str]): Bayes-related SpamAssassin rules.

    Returns:
        str | None: Highest-ranked known Bayes rule, or None if absent.
    """

    known_rules = [rule for rule in bayes_rules if rule in BAYES_RULE_RANK]
    if not known_rules:
        return None

    return max(known_rules, key=lambda rule: BAYES_RULE_RANK[rule])


# --------------------------------------------------
# Main analysis function
# --------------------------------------------------

def run_bayes_analysis_spamassassin(
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
):
    """
    Analyze SpamAssassin Bayes behavior for baseline-detected spam and salted variants.

    Args:
        results_csv (Path): Variant-level evaluation results.
        paired_csv (Path): Paired baseline and salted evaluation results.
        output_dir (Path): Directory for analysis artifacts.

    Returns:
        dict: Aggregated Bayes distributions, transitions, losses, and score statistics.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # Load paired CSV and identify baseline-detected spam
    # --------------------------------------------------

    baseline_detected_ids = set()

    with open(paired_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            baseline_spam = str(row.get("baseline_spam_flag", "")).strip().lower() == "true"
            if baseline_spam:
                baseline_detected_ids.add(row["message_id"])

    # --------------------------------------------------
    # Load results CSV
    # --------------------------------------------------

    baseline_by_message = {}
    salted_by_message = defaultdict(list)

    baseline_bayes_counts = Counter()
    salted_bayes_counts = Counter()

    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            if row["label"] != "spam":
                continue

            message_id = row["message_id"]
            if message_id not in baseline_detected_ids:
                continue

            bayes_rules = _extract_bayes_rules(row.get("rules", ""))

            if row["dataset"] == "baseline":
                strongest_bayes = _strongest_bayes_rule(bayes_rules)

                baseline_by_message[message_id] = {
                    "message_id": message_id,
                    "bayes_rules": bayes_rules,
                    "strongest_bayes": strongest_bayes,
                }

                for rule in bayes_rules:
                    baseline_bayes_counts[rule] += 1

            elif row["dataset"] == "salted":
                strongest_bayes = _strongest_bayes_rule(bayes_rules)

                salted_by_message[message_id].append(
                    {
                        "variant_filename": row.get("variant_filename", ""),
                        "codepoint": row.get("codepoint", ""),
                        "bayes_rules": bayes_rules,
                        "strongest_bayes": strongest_bayes,
                    }
                )

                for rule in bayes_rules:
                    salted_bayes_counts[rule] += 1

    # --------------------------------------------------
    # Per-email transition analysis
    # --------------------------------------------------

    transition_rows = []
    transition_counter = Counter()

    n_baseline_with_bayes = 0
    n_salted_with_any_bayes = 0
    n_bayes_lost_any = 0
    n_bayes_lost_all = 0

    for message_id, baseline_info in baseline_by_message.items():
        variants = salted_by_message.get(message_id, [])
        if not variants:
            continue

        baseline_rule = baseline_info["strongest_bayes"]
        variant_rules = [v["strongest_bayes"] for v in variants]

        salted_any_bayes = any(rule is not None for rule in variant_rules)
        salted_all_bayes = all(rule is not None for rule in variant_rules)

        salted_strongest_best = None
        present_variant_rules = [rule for rule in variant_rules if rule is not None]
        if present_variant_rules:
            salted_strongest_best = max(
                present_variant_rules,
                key=lambda rule: BAYES_RULE_RANK.get(rule, -1),
            )

        if baseline_rule is not None:
            n_baseline_with_bayes += 1

        if salted_any_bayes:
            n_salted_with_any_bayes += 1

        if baseline_rule is not None:
            if not salted_all_bayes:
                # At least one salted variant lost the Bayes signal
                n_bayes_lost_any += 1
            if not salted_any_bayes:
                # All salted variants lost the Bayes signal
                n_bayes_lost_all += 1

        transition_key = (
            baseline_rule if baseline_rule is not None else "none",
            salted_strongest_best if salted_strongest_best is not None else "none",
        )
        transition_counter[transition_key] += 1

        transition_rows.append(
            {
                "message_id": message_id,
                "baseline_bayes": baseline_rule if baseline_rule is not None else "none",
                "salted_best_bayes": salted_strongest_best if salted_strongest_best is not None else "none",
                "n_variants": len(variants),
                "salted_any_bayes": salted_any_bayes,
                "salted_all_bayes": salted_all_bayes,
            }
        )

    transition_rows.sort(key=lambda row: row["message_id"])

    baseline_bayes_scores = [
        BAYES_RULE_SCORE[info["strongest_bayes"]]
        for info in baseline_by_message.values()
        if info["strongest_bayes"] in BAYES_RULE_SCORE
    ]

    salted_bayes_scores = [
        BAYES_RULE_SCORE[v["strongest_bayes"]]
        for variants in salted_by_message.values()
        for v in variants
        if v["strongest_bayes"] in BAYES_RULE_SCORE
    ]

    baseline_bayes_score_mean = (
        round(sum(baseline_bayes_scores) / len(baseline_bayes_scores), 6)
        if baseline_bayes_scores else None
    )
    salted_bayes_score_mean = (
        round(sum(salted_bayes_scores) / len(salted_bayes_scores), 6)
        if salted_bayes_scores else None
    )

    # --------------------------------------------------
    # Write per-email transition CSV
    # --------------------------------------------------

    bayes_analysis_csv = output_dir / "bayes_analysis.csv"

    with open(bayes_analysis_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "message_id",
                "baseline_bayes",
                "salted_best_bayes",
                "n_variants",
                "salted_any_bayes",
                "salted_all_bayes",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(transition_rows)

    # --------------------------------------------------
    # Write Bayes level counts CSV
    # --------------------------------------------------

    bayes_level_counts_csv = output_dir / "bayes_level_counts.csv"

    level_rows = []
    for rule in BAYES_RULE_ORDER:
        level_rows.append(
            {
                "bayes_rule": rule,
                "baseline_count": baseline_bayes_counts.get(rule, 0),
                "salted_count": salted_bayes_counts.get(rule, 0),
            }
        )

    with open(bayes_level_counts_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "bayes_rule",
                "baseline_count",
                "salted_count",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(level_rows)

    # --------------------------------------------------
    # Build summary
    # --------------------------------------------------

    transition_summary = []
    for (baseline_rule, salted_rule), count in transition_counter.most_common():
        transition_summary.append(
            {
                "baseline_bayes": baseline_rule,
                "salted_best_bayes": salted_rule,
                "count": count,
            }
        )

    summary = {
        "n_baseline_detected_emails": len(baseline_by_message),
        "n_baseline_with_bayes": n_baseline_with_bayes,
        "n_salted_with_any_bayes": n_salted_with_any_bayes,
        "n_bayes_lost_any": n_bayes_lost_any,
        "n_bayes_lost_all": n_bayes_lost_all,
        "baseline_bayes_score_mean": baseline_bayes_score_mean,
        "salted_bayes_score_mean": salted_bayes_score_mean,
        "baseline_bayes_level_counts": {
            rule: baseline_bayes_counts.get(rule, 0) for rule in BAYES_RULE_ORDER
        },
        "salted_bayes_level_counts": {
            rule: salted_bayes_counts.get(rule, 0) for rule in BAYES_RULE_ORDER
        },
        "bayes_transitions": transition_summary,
    }

    # --------------------------------------------------
    # Write JSON summary
    # --------------------------------------------------

    bayes_analysis_json = output_dir / "bayes_analysis.json"

    with open(bayes_analysis_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print_step("Bayes Analysis")

    print_section("Output files")
    print_kv("bayes_analysis_csv", bayes_analysis_csv)
    print_kv("bayes_level_counts_csv", bayes_level_counts_csv)
    print_kv("bayes_analysis_json", bayes_analysis_json)

    print_end("Bayes Analysis")

    return summary