#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median

from src.main_evaluation.analysis.rule_loss_analysis import run_rule_loss_analysis
from src.utils.console import print_step, print_section, print_kv, print_end
from src.main_evaluation.analysis.bayes_analysis_spamassassin import run_bayes_analysis_spamassassin
from src.main_evaluation.analysis.bayes_analysis_rspamd import run_bayes_analysis_rspamd


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


def _to_int(value):
    if value in (None, "", "None"):
        return None
    return int(float(value))


def _safe_mean(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def _safe_median(values):
    values = [v for v in values if v is not None]
    return median(values) if values else None


def _safe_rate(num: int, denom: int):
    if denom == 0:
        return None
    return num / denom


def _round_or_none(value, ndigits=6):
    if value is None:
        return None
    return round(value, ndigits)


def build_experiment_summary(
    experiment_id: str,
    results_csv: Path,
    paired_csv: Path,
    output_dir: Path,
    filter_name: str | None = None,
    mechanism: str | None = None,
    rule_scope: str | None = None,
    salting_condition: str | None = None,
):
    results_rows = _read_csv(results_csv)
    paired_rows = _read_csv(paired_csv)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json_path = output_dir / "summary.json"
    summary_txt_path = output_dir / "summary.txt"

    # -----------------------------
    # Normalize variant-level rows
    # -----------------------------
    normalized_results = []
    for row in results_rows:
        normalized_results.append(
            {
                "dataset": row.get("dataset", ""),
                "label": row.get("label", ""),
                "message_id": row.get("message_id", ""),
                "variant_filename": row.get("variant_filename", ""),
                "vocab_type": row.get("vocab_type", ""),
                "codepoint": row.get("codepoint", ""),
                "spam_flag": _to_bool(row.get("spam_flag")),
                "score": _to_float(row.get("score")),
                "threshold": _to_float(row.get("threshold")),
                "rule_count": _to_int(row.get("rule_count")),
                "rules": row.get("rules", ""),
                "n_insert_subject": _to_int(row.get("n_insert_subject")),
                "n_insert_body": _to_int(row.get("n_insert_body")),
            }
        )

    # -----------------------------
    # Normalize paired rows
    # -----------------------------
    normalized_paired = []
    for row in paired_rows:
        baseline_score = _to_float(row.get("baseline_score"))
        baseline_rule_count = _to_int(row.get("baseline_rule_count"))
        salted_score_mean = _to_float(row.get("salted_score_mean"))
        salted_score_min = _to_float(row.get("salted_score_min"))
        salted_score_max = _to_float(row.get("salted_score_max"))
        salted_rule_count_mean = _to_float(row.get("salted_rule_count_mean"))

        normalized_paired.append(
            {
                "message_id": row.get("message_id", ""),
                "baseline_score": baseline_score,
                "baseline_spam_flag": _to_bool(row.get("baseline_spam_flag")),
                "baseline_rule_count": baseline_rule_count,
                "n_variants": _to_int(row.get("n_variants")) or 0,
                "salted_score_mean": salted_score_mean,
                "salted_score_min": salted_score_min,
                "salted_score_max": salted_score_max,
                "salted_rule_count_mean": salted_rule_count_mean,
                "salted_any_spam": _to_bool(row.get("salted_any_spam")),
                "salted_all_spam": _to_bool(row.get("salted_all_spam")),
                "salted_any_bypass": _to_bool(row.get("salted_any_bypass")),
                "salted_all_bypass": _to_bool(row.get("salted_all_bypass")),
                "score_drop_mean": (
                    baseline_score - salted_score_mean
                    if baseline_score is not None and salted_score_mean is not None
                    else None
                ),
                "score_drop_best_case": (
                    baseline_score - salted_score_min
                    if baseline_score is not None and salted_score_min is not None
                    else None
                ),
                "rule_loss_mean": (
                    baseline_rule_count - salted_rule_count_mean
                    if baseline_rule_count is not None and salted_rule_count_mean is not None
                    else None
                ),
            }
        )

    # -----------------------------
    # Variant-level subsets
    # -----------------------------
    baseline_spam_rows = [
        r for r in normalized_results
        if r["dataset"] == "baseline" and r["label"] == "spam"
    ]
    baseline_ham_rows = [
        r for r in normalized_results
        if r["dataset"] == "baseline" and r["label"] == "ham"
    ]
    salted_spam_rows = [
        r for r in normalized_results
        if r["dataset"] == "salted" and r["label"] == "spam"
    ]

    # -----------------------------
    # Paired-level subsets
    # -----------------------------
    paired_all = normalized_paired
    paired_baseline_detected = [r for r in paired_all if r["baseline_spam_flag"]]
    paired_baseline_not_detected = [r for r in paired_all if not r["baseline_spam_flag"]]

    # -----------------------------
    # Counts
    # -----------------------------
    n_baseline_spam = len(baseline_spam_rows)
    n_baseline_ham = len(baseline_ham_rows)
    n_salted_variants = len(salted_spam_rows)
    n_unique_salted_sources = len({r["message_id"] for r in salted_spam_rows if r["message_id"]})

    n_paired_rows = len(paired_all)
    n_baseline_detected_spam = len(paired_baseline_detected)
    n_baseline_not_detected_spam = len(paired_baseline_not_detected)

    # -----------------------------
    # Baseline performance
    # -----------------------------
    n_baseline_spam_detected = sum(1 for r in baseline_spam_rows if r["spam_flag"])
    n_baseline_ham_false_positive = sum(1 for r in baseline_ham_rows if r["spam_flag"])

    baseline_spam_detection_rate = _safe_rate(n_baseline_spam_detected, n_baseline_spam)
    baseline_ham_false_positive_rate = _safe_rate(n_baseline_ham_false_positive, n_baseline_ham)

    # -----------------------------
    # Central metrics on paired baseline-detected spam
    # -----------------------------
    n_any_bypass = sum(1 for r in paired_baseline_detected if r["salted_any_bypass"])
    n_all_bypass = sum(1 for r in paired_baseline_detected if r["salted_all_bypass"])
    n_all_spam = sum(1 for r in paired_baseline_detected if r["salted_all_spam"])
    n_any_spam = sum(1 for r in paired_baseline_detected if r["salted_any_spam"])

    bypass_rate_any = _safe_rate(n_any_bypass, n_baseline_detected_spam)
    bypass_rate_all = _safe_rate(n_all_bypass, n_baseline_detected_spam)

    classification_stability_all_spam = _safe_rate(n_all_spam, n_baseline_detected_spam)
    classification_stability_any_spam = _safe_rate(n_any_spam, n_baseline_detected_spam)

    mean_score_drop = _safe_mean([r["score_drop_mean"] for r in paired_baseline_detected])
    median_score_drop = _safe_median([r["score_drop_mean"] for r in paired_baseline_detected])

    mean_best_case_score_drop = _safe_mean(
        [r["score_drop_best_case"] for r in paired_baseline_detected]
    )
    median_best_case_score_drop = _safe_median(
        [r["score_drop_best_case"] for r in paired_baseline_detected]
    )

    mean_rule_loss = _safe_mean([r["rule_loss_mean"] for r in paired_baseline_detected])
    median_rule_loss = _safe_median([r["rule_loss_mean"] for r in paired_baseline_detected])

    mean_baseline_score = _safe_mean([r["baseline_score"] for r in paired_baseline_detected])
    mean_salted_score_mean = _safe_mean([r["salted_score_mean"] for r in paired_baseline_detected])
    mean_salted_score_min = _safe_mean([r["salted_score_min"] for r in paired_baseline_detected])

    mean_baseline_rule_count = _safe_mean(
        [r["baseline_rule_count"] for r in paired_baseline_detected]
    )
    mean_salted_rule_count = _safe_mean(
        [r["salted_rule_count_mean"] for r in paired_baseline_detected]
    )

    # -----------------------------
    # Codepoint analysis
    # -----------------------------
    baseline_detected_ids = {
        r["message_id"] for r in paired_baseline_detected if r["message_id"]
    }

    codepoint_summary = {}
    for codepoint in sorted({r["codepoint"] for r in salted_spam_rows if r["codepoint"]}):
        cp_rows = [r for r in salted_spam_rows if r["codepoint"] == codepoint]
        cp_detected_rows = [r for r in cp_rows if r["message_id"] in baseline_detected_ids]

        n_cp_variants = len(cp_rows)
        n_cp_unique_sources = len({r["message_id"] for r in cp_rows if r["message_id"]})
        n_cp_detected_sources = len({r["message_id"] for r in cp_detected_rows if r["message_id"]})

        n_cp_bypass = sum(1 for r in cp_detected_rows if not r["spam_flag"])
        n_cp_spam = sum(1 for r in cp_detected_rows if r["spam_flag"])

        cp_scores = [r["score"] for r in cp_detected_rows]
        cp_rule_counts = [r["rule_count"] for r in cp_detected_rows]

        codepoint_summary[codepoint] = {
            "n_variants": n_cp_variants,
            "n_unique_sources": n_cp_unique_sources,
            "n_baseline_detected_sources": n_cp_detected_sources,
            "bypass_rate": _round_or_none(_safe_rate(n_cp_bypass, n_cp_detected_sources)),
            "spam_rate": _round_or_none(_safe_rate(n_cp_spam, n_cp_detected_sources)),
            "mean_score": _round_or_none(_safe_mean(cp_scores)),
            "median_score": _round_or_none(_safe_median(cp_scores)),
            "mean_rule_count": _round_or_none(_safe_mean(cp_rule_counts)),
        }

    # -----------------------------
    # Salting intensity analysis
    # -----------------------------
    subject_insertions = [
        r["n_insert_subject"] for r in salted_spam_rows
        if r.get("n_insert_subject") is not None
    ]

    body_insertions = [
        r["n_insert_body"] for r in salted_spam_rows
        if r.get("n_insert_body") is not None
    ]

    salting_intensity = {
        "mean_subject_insertions": _round_or_none(_safe_mean(subject_insertions)),
        "mean_body_insertions": _round_or_none(_safe_mean(body_insertions)),
        "mean_total_insertions": _round_or_none(
            _safe_mean([(s or 0) + (b or 0) for s, b in zip(subject_insertions, body_insertions)])
        ),
        "max_subject_insertions": max(subject_insertions) if subject_insertions else 0,
        "max_body_insertions": max(body_insertions) if body_insertions else 0,
    }

    # -----------------------------
    # Insertion distribution
    # -----------------------------
    total_insertions = [
        (r.get("n_insert_subject") or 0) + (r.get("n_insert_body") or 0)
        for r in salted_spam_rows
    ]

    insertion_distribution = {}

    for v in total_insertions:
        insertion_distribution[v] = insertion_distribution.get(v, 0) + 1

    # sort by insertion count
    insertion_distribution = dict(sorted(insertion_distribution.items()))

    # -----------------------------
    # Bayes analysis
    # -----------------------------
    if filter_name == "Rspamd":
        bayes_summary = run_bayes_analysis_rspamd(
            results_csv=results_csv,
            paired_csv=paired_csv,
            output_dir=output_dir,
        )
    else:
        bayes_summary = run_bayes_analysis_spamassassin(
            results_csv=results_csv,
            paired_csv=paired_csv,
            output_dir=output_dir,
        )

    # -----------------------------
    # Rule loss analysis
    # -----------------------------
    rule_loss_summary = run_rule_loss_analysis(
        results_csv=results_csv,
        paired_csv=paired_csv,
        output_dir=output_dir,
    )

    # -----------------------------
    # Summary object
    # -----------------------------
    summary = {
        "experiment_id": experiment_id,
        "filter": filter_name,
        "mechanism": mechanism,
        "rule_scope": rule_scope,
        "salting_condition": salting_condition,
        "inputs": {
            "results_csv": str(results_csv),
            "paired_csv": str(paired_csv),
        },
        "counts": {
            "n_variant_rows_total": len(normalized_results),
            "n_paired_rows_total": n_paired_rows,
            "n_baseline_spam": n_baseline_spam,
            "n_baseline_ham": n_baseline_ham,
            "n_salted_variants": n_salted_variants,
            "n_unique_salted_sources": n_unique_salted_sources,
            "n_baseline_detected_spam": n_baseline_detected_spam,
            "n_baseline_not_detected_spam": n_baseline_not_detected_spam,
            "n_baseline_spam_detected_variant_level": n_baseline_spam_detected,
            "n_baseline_ham_false_positive": n_baseline_ham_false_positive,
        },
        "rates": {
            "baseline_spam_detection_rate": _round_or_none(baseline_spam_detection_rate),
            "baseline_ham_false_positive_rate": _round_or_none(baseline_ham_false_positive_rate),
            "bypass_rate_any": _round_or_none(bypass_rate_any),
            "bypass_rate_all": _round_or_none(bypass_rate_all),
            "classification_stability_all_spam": _round_or_none(classification_stability_all_spam),
            "classification_stability_any_spam": _round_or_none(classification_stability_any_spam),
        },
        "means": {
            "mean_baseline_score": _round_or_none(mean_baseline_score),
            "mean_salted_score_mean": _round_or_none(mean_salted_score_mean),
            "mean_salted_score_min": _round_or_none(mean_salted_score_min),
            "mean_score_drop": _round_or_none(mean_score_drop),
            "mean_best_case_score_drop": _round_or_none(mean_best_case_score_drop),
            "mean_baseline_rule_count": _round_or_none(mean_baseline_rule_count),
            "mean_salted_rule_count": _round_or_none(mean_salted_rule_count),
            "mean_rule_loss": _round_or_none(mean_rule_loss),
        },
        "medians": {
            "median_score_drop": _round_or_none(median_score_drop),
            "median_best_case_score_drop": _round_or_none(median_best_case_score_drop),
            "median_rule_loss": _round_or_none(median_rule_loss),
        },
        "classification_counts": {
            "n_any_bypass": n_any_bypass,
            "n_all_bypass": n_all_bypass,
            "n_all_spam": n_all_spam,
            "n_any_spam": n_any_spam,
        },
        "codepoints": codepoint_summary,
        "salting_intensity": salting_intensity,
        "insertion_distribution": insertion_distribution,
        "bayes_analysis": bayes_summary,
        "rule_loss_analysis": rule_loss_summary,
    }

    # -----------------------------
    # Write JSON
    # -----------------------------
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # -----------------------------
    # Write TXT
    # -----------------------------
    lines = []
    lines.append(f"Experiment Summary: {experiment_id}")
    lines.append("=" * (20 + len(experiment_id)))
    lines.append("")
    lines.append(f"Filter              : {filter_name}")
    lines.append(f"Mechanism           : {mechanism}")
    lines.append(f"Rule scope          : {rule_scope}")
    lines.append(f"Salting condition   : {salting_condition}")
    lines.append("")
    lines.append("Input files")
    lines.append("-----------")
    lines.append(f"results.csv         : {results_csv}")
    lines.append(f"results_paired.csv  : {paired_csv}")
    lines.append("")
    lines.append("Counts")
    lines.append("------")
    lines.append(f"Variant rows total              : {len(normalized_results)}")
    lines.append(f"Paired rows total               : {n_paired_rows}")
    lines.append(f"Baseline spam                   : {n_baseline_spam}")
    lines.append(f"Baseline ham                    : {n_baseline_ham}")
    lines.append(f"Salted variants                 : {n_salted_variants}")
    lines.append(f"Unique salted source emails     : {n_unique_salted_sources}")
    lines.append(f"Baseline-detected spam          : {n_baseline_detected_spam}")
    lines.append(f"Baseline-not-detected spam      : {n_baseline_not_detected_spam}")
    lines.append(f"Baseline spam detected (variant): {n_baseline_spam_detected}")
    lines.append(f"Baseline ham false positives    : {n_baseline_ham_false_positive}")
    lines.append("")
    lines.append("Rates")
    lines.append("-----")
    lines.append(f"Baseline spam detection rate    : {summary['rates']['baseline_spam_detection_rate']}")
    lines.append(f"Baseline ham FP rate            : {summary['rates']['baseline_ham_false_positive_rate']}")
    lines.append(f"Bypass rate (any)               : {summary['rates']['bypass_rate_any']}")
    lines.append(f"Bypass rate (all)               : {summary['rates']['bypass_rate_all']}")
    lines.append(f"Classification stability (all)  : {summary['rates']['classification_stability_all_spam']}")
    lines.append(f"Classification stability (any)  : {summary['rates']['classification_stability_any_spam']}")
    lines.append("")
    lines.append("Means")
    lines.append("-----")
    lines.append(f"Mean baseline score             : {summary['means']['mean_baseline_score']}")
    lines.append(f"Mean salted score               : {summary['means']['mean_salted_score_mean']}")
    lines.append(f"Mean salted min score           : {summary['means']['mean_salted_score_min']}")
    lines.append(f"Mean score drop                 : {summary['means']['mean_score_drop']}")
    lines.append(f"Mean best-case score drop       : {summary['means']['mean_best_case_score_drop']}")
    lines.append(f"Mean baseline rule count        : {summary['means']['mean_baseline_rule_count']}")
    lines.append(f"Mean salted rule count          : {summary['means']['mean_salted_rule_count']}")
    lines.append(f"Mean rule loss                  : {summary['means']['mean_rule_loss']}")
    lines.append("")
    lines.append("Medians")
    lines.append("-------")
    lines.append(f"Median score drop               : {summary['medians']['median_score_drop']}")
    lines.append(f"Median best-case score drop     : {summary['medians']['median_best_case_score_drop']}")
    lines.append(f"Median rule loss                : {summary['medians']['median_rule_loss']}")
    lines.append("")
    lines.append("Classification counts")
    lines.append("---------------------")
    lines.append(f"n_any_bypass                    : {n_any_bypass}")
    lines.append(f"n_all_bypass                    : {n_all_bypass}")
    lines.append(f"n_all_spam                      : {n_all_spam}")
    lines.append(f"n_any_spam                      : {n_any_spam}")
    lines.append("")
    lines.append("Codepoint analysis")
    lines.append("------------------")

    if not codepoint_summary:
        lines.append("No codepoint data available.")
    else:
        for cp, cp_data in codepoint_summary.items():
            lines.append(f"{cp}:")
            lines.append(f"  n_variants                  : {cp_data['n_variants']}")
            lines.append(f"  n_unique_sources            : {cp_data['n_unique_sources']}")
            lines.append(f"  n_baseline_detected_sources : {cp_data['n_baseline_detected_sources']}")
            lines.append(f"  bypass_rate                 : {cp_data['bypass_rate']}")
            lines.append(f"  spam_rate                   : {cp_data['spam_rate']}")
            lines.append(f"  mean_score                  : {cp_data['mean_score']}")
            lines.append(f"  median_score                : {cp_data['median_score']}")
            lines.append(f"  mean_rule_count             : {cp_data['mean_rule_count']}")
            lines.append("")

    lines.append("Salting intensity")
    lines.append("-----------------")

    si = summary.get("salting_intensity", {})

    lines.append(f"Mean subject insertions : {si.get('mean_subject_insertions')}")
    lines.append(f"Mean body insertions    : {si.get('mean_body_insertions')}")
    lines.append(f"Mean total insertions   : {si.get('mean_total_insertions')}")
    lines.append(f"Max subject insertions  : {si.get('max_subject_insertions')}")
    lines.append(f"Max body insertions     : {si.get('max_body_insertions')}")
    lines.append("")

    # -----------------------------
    # Insertion distribution
    # -----------------------------
    lines.append("Insertion distribution")
    lines.append("----------------------")

    dist = summary.get("insertion_distribution", {})

    if not dist:
        lines.append("No insertion data available.")
    else:
        for k, v in dist.items():
            lines.append(f"{k} insertions : {v}")

    lines.append("")

    lines.append("Bayes analysis")
    lines.append("--------------")

    bayes_data = summary.get("bayes_analysis", {})

    lines.append(f"Baseline-detected emails         : {bayes_data.get('n_baseline_detected_emails')}")
    lines.append(f"Baseline emails with Bayes       : {bayes_data.get('n_baseline_with_bayes')}")
    lines.append(f"Salted emails with any Bayes     : {bayes_data.get('n_salted_with_any_bayes')}")
    lines.append(f"Bayes lost in at least one var.  : {bayes_data.get('n_bayes_lost_any')}")
    lines.append(f"Bayes lost in all variants       : {bayes_data.get('n_bayes_lost_all')}")
    lines.append("")

    if filter_name == "Rspamd":
        baseline_bayes_counts = bayes_data.get("baseline_bayes_symbol_counts", {})
        salted_bayes_counts = bayes_data.get("salted_bayes_symbol_counts", {})

        lines.append(f"Mean baseline Bayes score        : {bayes_data.get('baseline_bayes_score_mean')}")
        lines.append(f"Mean salted Bayes score          : {bayes_data.get('salted_bayes_score_mean')}")
        lines.append("")

        lines.append("Baseline Bayes symbols")
        lines.append("~~~~~~~~~~~~~~~~~~~~~~")
        if not baseline_bayes_counts:
            lines.append("No Bayes symbol data available.")
        else:
            for rule, count in baseline_bayes_counts.items():
                lines.append(f"{rule}:")
                lines.append(f"  count : {count}")
                lines.append("")

        lines.append("Salted Bayes symbols")
        lines.append("~~~~~~~~~~~~~~~~~~~~")
        if not salted_bayes_counts:
            lines.append("No Bayes symbol data available.")
        else:
            for rule, count in salted_bayes_counts.items():
                lines.append(f"{rule}:")
                lines.append(f"  count : {count}")
                lines.append("")
    else:
        baseline_bayes_counts = bayes_data.get("baseline_bayes_level_counts", {})
        salted_bayes_counts = bayes_data.get("salted_bayes_level_counts", {})
        bayes_transitions = bayes_data.get("bayes_transitions", [])

        lines.append("Baseline Bayes rule levels")
        lines.append("~~~~~~~~~~~~~~~~~~~~~~~~~~")
        if not baseline_bayes_counts:
            lines.append("No Bayes data available.")
        else:
            for rule, count in baseline_bayes_counts.items():
                lines.append(f"{rule}:")
                lines.append(f"  count : {count}")
                lines.append("")

        lines.append("Salted Bayes rule levels")
        lines.append("~~~~~~~~~~~~~~~~~~~~~~~~")
        if not salted_bayes_counts:
            lines.append("No Bayes data available.")
        else:
            for rule, count in salted_bayes_counts.items():
                lines.append(f"{rule}:")
                lines.append(f"  count : {count}")
                lines.append("")

        lines.append("Bayes transitions")
        lines.append("~~~~~~~~~~~~~~~~~")
        if not bayes_transitions:
            lines.append("No Bayes transition data available.")
        else:
            for row in bayes_transitions:
                lines.append(f"{row['baseline_bayes']} -> {row['salted_best_bayes']}:")
                lines.append(f"  count : {row['count']}")
                lines.append("")

    # -----------------------------
    # Rule loss analysis
    # -----------------------------
    lines.append("Rule loss analysis")
    lines.append("------------------")

    rule_loss = summary.get("rule_loss_analysis", {})
    all_rule_loss = rule_loss.get("all_rule_loss", [])
    all_bypass_rule_loss = rule_loss.get("all_bypass_rule_loss", [])

    if not all_rule_loss:
        lines.append("No rule loss data available.")
    else:
        lines.append("Lost rules (all)")
        lines.append("~~~~~~~~~~~~~~~~")
        for r in all_rule_loss:
            lines.append(f"{r['rule']}:")
            lines.append(f"  baseline_occurrences  : {r['baseline_occurrences']}")
            lines.append(f"  lost_in_any_variant   : {r['lost_in_any_variant']}")
            lines.append(f"  lost_in_all_variants  : {r['lost_in_all_variants']}")
            lines.append(f"  lost_rate_any_variant : {r['lost_rate_any_variant']}")
            lines.append(f"  lost_rate_all_variants: {r['lost_rate_all_variants']}")
            lines.append("")

    if not all_bypass_rule_loss:
        lines.append("No bypass rule loss data available.")
    else:
        lines.append("Lost rules in bypass cases")
        lines.append("~~~~~~~~~~~~~~~~~~~~~~~~~~")
        for r in all_bypass_rule_loss:
            lines.append(f"{r['rule']}:")
            lines.append(f"  lost_in_bypass_any  : {r['lost_in_bypass_any']}")
            lines.append(f"  lost_in_bypass_all  : {r['lost_in_bypass_all']}")
            lines.append(f"  bypass_loss_rate_any: {r['bypass_loss_rate_any']}")
            lines.append(f"  bypass_loss_rate_all: {r['bypass_loss_rate_all']}")
            lines.append("")

    with open(summary_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print_step("Experiment Summary")

    print_section("Output files")
    print_kv("summary_json", summary_json_path)
    print_kv("summary_txt", summary_txt_path)

    print_end("Experiment Summary")

    return summary