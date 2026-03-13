#!/usr/bin/env python3
"""
Rule-loss analysis for SpamAssassin experiments.

This module analyzes how Unicode salting affects SpamAssassin rule triggering.

Purpose
-------
The goal of this analysis step is to determine which SpamAssassin rules
stop firing after Unicode salting has been applied to spam emails.

Two analyses are performed:

1. Global rule loss
   For every rule that fires on baseline spam emails, the module measures
   how often this rule disappears in salted variants.

2. Bypass rule loss
   For emails where salting causes a classification bypass
   (i.e. baseline detected as spam but salted classified as ham),
   the module identifies which rules were lost.

These results help explain why a filter score decreases after salting.

Inputs
------
spamassassin_results.csv
    Variant-level evaluation results produced by the SpamAssassin runner.

spamassassin_results_paired.csv
    Paired baseline vs salted comparison results.

Outputs
-------
rule_loss_analysis.csv
    Global statistics on rule disappearance rates.

bypass_rule_loss.csv
    Rules that disappear specifically in successful bypass cases.

The results are also returned as a dictionary so that they can be integrated
into the experiment summary.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from src.utils.console import print_step, print_section, print_kv, print_end
from src.utils.console import print_step, print_section


def _parse_rules(rule_string: str) -> set[str]:
    """
    Convert the rule string stored in the results CSV into a Python set.

    SpamAssassin rules are stored as a pipe-separated string, e.g.

        HTML_MESSAGE|DRUGS_ERECTILE|SUBJ_FREE

    This function converts the string into a set for easier comparison.

    The value "none" is ignored because it does not represent a real rule.
    """
    if not rule_string:
        return set()

    return {
        rule.strip()
        for rule in rule_string.split("|")
        if rule.strip() and rule.strip().lower() != "none"
    }


def run_rule_loss_analysis(
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
):
    """
    Perform rule-loss analysis.

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
    # Load results.csv
    # --------------------------------------------------

    baseline_rules_by_message = {}
    salted_rules_by_message = {}

    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            if row["label"] != "spam":
                continue

            message_id = row["message_id"]
            rules = _parse_rules(row["rules"])

            if row["dataset"] == "baseline":
                baseline_rules_by_message[message_id] = rules

            elif row["dataset"] == "salted":
                salted_rules_by_message.setdefault(message_id, []).append(rules)

    # --------------------------------------------------
    # Global rule-loss statistics
    # --------------------------------------------------
    # Important:
    # We count loss on the original-email level, not on the variant level.
    # This keeps loss rates in the range [0, 1].
    # --------------------------------------------------

    baseline_occurrences = Counter()
    lost_in_any_variant = Counter()
    lost_in_all_variants = Counter()

    for message_id, base_rules in baseline_rules_by_message.items():
        variant_rule_sets = salted_rules_by_message.get(message_id, [])

        if not variant_rule_sets:
            continue

        for rule in base_rules:
            baseline_occurrences[rule] += 1

            lost_flags = [rule not in variant_rules for variant_rules in variant_rule_sets]

            if any(lost_flags):
                lost_in_any_variant[rule] += 1

            if all(lost_flags):
                lost_in_all_variants[rule] += 1

    rule_loss_rows = []

    for rule, baseline_count in baseline_occurrences.items():
        lost_any = lost_in_any_variant.get(rule, 0)
        lost_all = lost_in_all_variants.get(rule, 0)

        if lost_any == 0:
            continue

        rule_loss_rows.append(
            {
                "rule": rule,
                "baseline_occurrences": baseline_count,
                "lost_in_any_variant": lost_any,
                "lost_in_all_variants": lost_all,
                "lost_rate_any_variant": round(lost_any / baseline_count, 6) if baseline_count else 0,
                "lost_rate_all_variants": round(lost_all / baseline_count, 6) if baseline_count else 0,
            }
        )

    rule_loss_rows.sort(
        key=lambda row: (
            row["lost_rate_any_variant"],
            row["lost_rate_all_variants"],
            row["baseline_occurrences"],
            row["rule"],
        ),
        reverse=True,
    )

    rule_loss_csv = output_dir / "rule_loss_analysis.csv"

    with open(rule_loss_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rule",
                "baseline_occurrences",
                "lost_in_any_variant",
                "lost_in_all_variants",
                "lost_rate_any_variant",
                "lost_rate_all_variants",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rule_loss_rows)

    # --------------------------------------------------
    # Load paired CSV to detect bypass cases
    # --------------------------------------------------

    bypass_ids = set()

    with open(paired_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            baseline_spam = str(row["baseline_spam_flag"]).strip().lower() == "true"
            bypass = str(row["salted_any_bypass"]).strip().lower() == "true"

            if baseline_spam and bypass:
                bypass_ids.add(row["message_id"])

    # --------------------------------------------------
    # Bypass rule loss analysis
    # --------------------------------------------------
    # Again, count on original-email level.
    # --------------------------------------------------

    bypass_rule_any = Counter()
    bypass_rule_all = Counter()

    for message_id in bypass_ids:
        base_rules = baseline_rules_by_message.get(message_id, set())
        variant_rule_sets = salted_rules_by_message.get(message_id, [])

        if not variant_rule_sets:
            continue

        for rule in base_rules:
            lost_flags = [rule not in variant_rules for variant_rules in variant_rule_sets]

            if any(lost_flags):
                bypass_rule_any[rule] += 1

            if all(lost_flags):
                bypass_rule_all[rule] += 1

    bypass_rows = []

    n_bypass_emails = len(bypass_ids)

    all_bypass_rules = set(bypass_rule_any.keys()) | set(bypass_rule_all.keys())

    for rule in sorted(all_bypass_rules):
        lost_any = bypass_rule_any.get(rule, 0)
        lost_all = bypass_rule_all.get(rule, 0)

        if lost_any == 0:
            continue

        bypass_rows.append(
            {
                "rule": rule,
                "lost_in_bypass_any": lost_any,
                "lost_in_bypass_all": lost_all,
                "bypass_loss_rate_any": round(lost_any / n_bypass_emails, 6) if n_bypass_emails else 0,
                "bypass_loss_rate_all": round(lost_all / n_bypass_emails, 6) if n_bypass_emails else 0,
            }
        )

    bypass_rows.sort(
        key=lambda row: (
            row["bypass_loss_rate_any"],
            row["bypass_loss_rate_all"],
            row["rule"],
        ),
        reverse=True,
    )

    bypass_csv = output_dir / "bypass_rule_loss.csv"

    with open(bypass_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rule",
                "lost_in_bypass_any",
                "lost_in_bypass_all",
                "bypass_loss_rate_any",
                "bypass_loss_rate_all",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(bypass_rows)

    summary = {
        "all_rule_loss": rule_loss_rows,
        "all_bypass_rule_loss": bypass_rows,
    }

    print_step("Rule Loss Analysis")

    print_section("Output files")
    print_kv("rule_loss_csv", rule_loss_csv)
    print_kv("bypass_rule_loss_csv", bypass_csv)

    print_end("Rule Loss Analysis")

    return summary