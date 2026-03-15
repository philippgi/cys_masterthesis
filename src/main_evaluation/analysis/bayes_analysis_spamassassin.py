#!/usr/bin/env python3
"""
Bayes analysis for SpamAssassin experiments.

This module analyzes Bayes-related rule behavior in SpamAssassin results.

Purpose
-------
The goal of this analysis step is to determine whether Unicode salting
affects SpamAssassin's Bayesian classification signals.

The module extracts all BAYES_* rules from the variant-level results and
compares baseline-detected spam emails with their salted variants.

Analyses performed
------------------
1. Baseline Bayes distribution
   Counts how often each BAYES_* rule level appears in baseline-detected
   spam emails.

2. Salted Bayes distribution
   Counts how often each BAYES_* rule level appears in salted variants of
   baseline-detected spam emails.

3. Bayes transition analysis
   Compares the strongest baseline BAYES_* rule of each original email with
   the strongest BAYES_* rule observed in its salted variants.

4. Bayes loss analysis
   Counts how often a baseline Bayes signal disappears completely in salted
   variants.

Inputs
------
spamassassin_results.csv
    Variant-level evaluation results produced by the SpamAssassin runner.

spamassassin_results_paired.csv
    Paired baseline vs salted comparison results.

Outputs
-------
bayes_analysis.csv
    Per-email Bayes transition statistics.

bayes_level_counts.csv
    Aggregated counts of BAYES_* rules in baseline and salted rows.

bayes_analysis.json
    Structured Bayes summary for further reuse.

The results are also returned as a dictionary so that they can be integrated
into the experiment summary.
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


# --------------------------------------------------
# Utility
# --------------------------------------------------

def _parse_rules(rule_string: str) -> list[str]:
    """
    Splits the pipe-separated SpamAssassin rule string into a list.

    The value "none" is ignored because it does not represent a real rule.
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
    Extracts all BAYES_* rules from a pipe-separated rule string.
    """
    return [rule for rule in _parse_rules(rule_string) if rule.startswith("BAYES_")]


def _strongest_bayes_rule(bayes_rules: list[str]) -> str | None:
    """
    Returns the strongest BAYES_* rule from a list.

    Strength is determined by BAYES_RULE_ORDER. Unknown BAYES_* rules are
    ignored.
    """
    known_rules = [rule for rule in bayes_rules if rule in BAYES_RULE_RANK]
    if not known_rules:
        return None

    return max(known_rules, key=lambda rule: BAYES_RULE_RANK[rule])


# --------------------------------------------------
# Main analysis function
# --------------------------------------------------

def run_bayes_analysis(
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
):
    """
    Perform Bayes analysis.

    Parameters
    ----------
    results_csv
        Path to spamassassin_results.csv.

    paired_csv
        Path to spamassassin_results_paired.csv.

    output_dir
        Directory where analysis outputs will be written.
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
            if not salted_any_bayes:
                n_bayes_lost_any += 1
            if not salted_all_bayes:
                # At least one salted variant lost the Bayes signal
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