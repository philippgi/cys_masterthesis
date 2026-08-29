#!/usr/bin/env python3
"""
Evaluates baseline and salted email variants with Rspamd.

The runner scans paired baseline spam messages, the complete ham test set,
and all generated salted spam variants. Rspamd responses are normalized into
variant-level results and aggregated into paired original-message results.
"""

from __future__ import annotations

import csv
import json
import http.client
import sys

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean
from tqdm import tqdm

from src.utils.console import print_step, print_section, print_kv, print_end
from config import (
    DATASET_SPLIT,
    OUTPUT_ROOT,
    RSPAMD_HOST,
    RSPAMD_PORT,
    RSPAMD_TIMEOUT,
)

# Limit concurrent HTTP scans to maintain stable Rspamd processing.
RSPAMD_MAX_WORKERS = 1


def load_salting_log(csv_path: Path) -> dict[str, dict[str, str]]:
    """
    Load salting metadata indexed by salted variant filename.

    Args:
        csv_path (Path): Path to the salting log.

    Returns:
        dict[str, dict[str, str]]: Salting metadata indexed by variant filename.
    """

    if not csv_path.exists():
        return {}

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["variant_filename"]: row for row in reader}


def load_salted_source_ids(csv_path: Path) -> set[str]:
    """
    Load original message IDs for which salted variants were generated.

    Args:
        csv_path (Path): Path to the salting log.

    Returns:
        set[str]: Original message IDs represented in the salted dataset.
    """

    if not csv_path.exists():
        return set()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["message_id"] for row in reader if row.get("message_id")}


def derive_salt_location(n_insert_subject, n_insert_body) -> str:
    """
    Derive the salting location from Subject and body insertion counts.

    Args:
        n_insert_subject: Number of Subject insertions.
        n_insert_body: Number of body insertions.

    Returns:
        str: One of "subject", "body", "both", or "none".
    """

    try:
        subject_count = int(n_insert_subject)
    except (TypeError, ValueError):
        subject_count = 0

    try:
        body_count = int(n_insert_body)
    except (TypeError, ValueError):
        body_count = 0

    if subject_count > 0 and body_count > 0:
        return "both"
    if subject_count > 0:
        return "subject"
    if body_count > 0:
        return "body"
    return "none"


def to_float_or_none(value):
    """Convert a value to float if possible, otherwise return None."""

    if value in (None, "", "None"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def determine_spam_flag(score, threshold, action: str) -> bool:
    """
    Determine the binary spam classification from the Rspamd result.

    Args:
        score: Rspamd message score.
        threshold: Configured add-header threshold.
        action (str): Rspamd action.

    Returns:
        bool: True if the message is classified as spam.
    """

    score_value = to_float_or_none(score)
    threshold_value = to_float_or_none(threshold)

    # Prefer the numeric add-header threshold; use the action only as a fallback.
    if score_value is not None and threshold_value is not None:
        return score_value >= threshold_value

    return action in {"add header", "reject", "soft reject"}


def extract_symbols(symbols_dict: dict) -> tuple[
    list[str],
    bool,
    str,
    float | None,
    bool,
    str,
    float | None,
]:
    """
    Extract rule, Bayes, and neural information from the Rspamd symbol response.

    Args:
        symbols_dict (dict): Symbol metadata returned by Rspamd.

    Returns:
        tuple: Symbol names, Bayes presence/name/score, and neural
        presence/name/score.
    """

    if not isinstance(symbols_dict, dict):
        return [], False, "", None, False, "", None

    symbol_names = sorted(symbols_dict.keys())

    best_bayes_symbol = ""
    best_bayes_score = None

    best_neural_symbol = ""
    best_neural_score = None

    for symbol_name, symbol_meta in symbols_dict.items():
        symbol_score = None
        if isinstance(symbol_meta, dict):
            symbol_score = to_float_or_none(symbol_meta.get("score"))

        if str(symbol_name).startswith("BAYES_"):
            if best_bayes_score is None or (
                symbol_score is not None and symbol_score > best_bayes_score
            ):
                best_bayes_symbol = str(symbol_name)
                best_bayes_score = symbol_score

        if str(symbol_name).startswith("NEURAL_"):
            if best_neural_score is None or (
                symbol_score is not None and (
                    best_neural_score is None or abs(symbol_score) > abs(best_neural_score)
                )
            ):
                best_neural_symbol = str(symbol_name)
                best_neural_score = symbol_score

    has_bayes = bool(best_bayes_symbol)
    has_neural = bool(best_neural_symbol)

    return (
        symbol_names,
        has_bayes,
        best_bayes_symbol,
        best_bayes_score,
        has_neural,
        best_neural_symbol,
        best_neural_score,
    )


def run_rspamd_scan(email_path: Path) -> dict:
    """
    Scan one RFC 5322 email through the Rspamd HTTP API.

    Args:
        email_path (Path): Path to the email message.

    Returns:
        dict: Normalized classification, score, symbol, Bayes, and neural data.

    Raises:
        RuntimeError: If Rspamd returns a non-successful HTTP status.
    """

    message_bytes = email_path.read_bytes()

    conn = http.client.HTTPConnection(
        host=RSPAMD_HOST,
        port=RSPAMD_PORT,
        timeout=RSPAMD_TIMEOUT,
    )

    try:
        conn.request(
            method="POST",
            url="/checkv2",
            body=message_bytes,
            headers={
                "Content-Type": "message/rfc822",
                "Content-Length": str(len(message_bytes)),
            },
        )

        response = conn.getresponse()
        response_body = response.read()

        if response.status != 200:
            raise RuntimeError(
                f"Rspamd returned HTTP {response.status}: "
                f"{response_body.decode('utf-8', errors='replace')}"
            )

        data = json.loads(response_body.decode("utf-8", errors="replace"))

    finally:
        conn.close()

    score = to_float_or_none(data.get("score"))
    thresholds = data.get("thresholds", {}) or {}
    threshold = to_float_or_none(thresholds.get("add header"))
    action = str(data.get("action", ""))

    symbols_dict = data.get("symbols", {}) or {}
    (
        symbol_names,
        has_bayes,
        bayes_symbol,
        bayes_score,
        has_neural,
        neural_symbol,
        neural_score,
    ) = extract_symbols(symbols_dict)

    spam_flag = determine_spam_flag(
        score=score,
        threshold=threshold,
        action=action,
    )

    return {
        "spam_flag": spam_flag,
        "score": score,
        "threshold": threshold,
        "action": action,
        "rule_count": len(symbol_names),
        "rules": "|".join(symbol_names),
        "has_bayes": has_bayes,
        "bayes_symbol": bayes_symbol,
        "bayes_score": bayes_score,
        "has_neural": has_neural,
        "neural_symbol": neural_symbol,
        "neural_score": neural_score,
        "raw_output": json.dumps(data, ensure_ascii=False),
    }


def evaluate_email(
    email_path: Path,
    dataset: str,
    label: str,
    message_id: str,
    variant_filename: str = "",
    salting_meta: dict | None = None,
) -> dict:
    """
    Scan one email and build its normalized variant-level result row.

    Args:
        email_path (Path): Path to the email message.
        dataset (str): Dataset type, such as baseline or salted.
        label (str): Ground-truth class label.
        message_id (str): Original message identifier.
        variant_filename (str): Salted variant filename, if applicable.
        salting_meta (dict | None): Associated salting metadata.

    Returns:
        dict: Normalized evaluation result row.
    """

    scan = run_rspamd_scan(email_path)

    salting_meta = salting_meta or {}
    n_insert_subject = salting_meta.get("n_insert_subject", "")
    n_insert_body = salting_meta.get("n_insert_body", "")

    return {
        "dataset": dataset,
        "label": label,
        "message_id": message_id,
        "variant_filename": variant_filename,
        "vocab_type": salting_meta.get("vocab_type", ""),
        "codepoint": salting_meta.get("codepoint", ""),
        "salt_location": derive_salt_location(n_insert_subject, n_insert_body),
        "n_insert_subject": n_insert_subject,
        "n_insert_body": n_insert_body,
        "spam_flag": scan["spam_flag"],
        "score": scan["score"],
        "threshold": scan["threshold"],
        "action": scan["action"],
        "rule_count": scan["rule_count"],
        "rules": scan["rules"],
        "has_bayes": scan["has_bayes"],
        "bayes_symbol": scan["bayes_symbol"],
        "bayes_score": scan["bayes_score"],
        "raw_output": scan["raw_output"],
        "has_neural": scan["has_neural"],
        "neural_symbol": scan["neural_symbol"],
        "neural_score": scan["neural_score"],
    }


def build_paired_results(rows: list[dict]) -> list[dict]:
    """
    Aggregate variant-level spam results on the original-message level.

    Each paired row combines one baseline spam email with all salted variants
    derived from that message.

    Args:
        rows (list[dict]): Variant-level evaluation results.

    Returns:
        list[dict]: Paired baseline and salted result rows.
    """

    baseline_by_message = {}
    salted_by_message = defaultdict(list)

    for row in rows:
        if row["label"] != "spam":
            continue

        if row["dataset"] == "baseline":
            baseline_by_message[row["message_id"]] = row
        elif row["dataset"] == "salted" and row["message_id"]:
            salted_by_message[row["message_id"]].append(row)

    paired_rows = []

    for message_id, baseline in baseline_by_message.items():
        variants = salted_by_message.get(message_id, [])
        if not variants:
            continue

        variant_scores = [v["score"] for v in variants if v["score"] is not None]
        variant_rule_counts = [v["rule_count"] for v in variants if v["rule_count"] is not None]
        variant_flags = [bool(v["spam_flag"]) for v in variants]
        variant_bypass = [not bool(v["spam_flag"]) for v in variants]

        paired_rows.append(
            {
                "message_id": message_id,
                "baseline_score": baseline["score"],
                "baseline_spam_flag": baseline["spam_flag"],
                "baseline_rule_count": baseline["rule_count"],
                "baseline_action": baseline["action"],
                "n_variants": len(variants),
                "salted_score_mean": mean(variant_scores) if variant_scores else None,
                "salted_score_min": min(variant_scores) if variant_scores else None,
                "salted_score_max": max(variant_scores) if variant_scores else None,
                "salted_rule_count_mean": mean(variant_rule_counts) if variant_rule_counts else None,
                "salted_any_spam": any(variant_flags),
                "salted_all_spam": all(variant_flags),
                "salted_any_bypass": any(variant_bypass),
                "salted_all_bypass": all(variant_bypass),
            }
        )

    paired_rows.sort(key=lambda row: row["message_id"])
    return paired_rows


def scan_batch(jobs: list[dict], desc: str) -> list[dict]:
    """
    Scan a batch of emails while preserving the original job order.

    Args:
        jobs (list[dict]): Email scan jobs.
        desc (str): Progress-bar description.

    Returns:
        list[dict]: Evaluation results in the same order as the input jobs.
    """

    if not jobs:
        return []

    results_by_index = {}

    with ThreadPoolExecutor(max_workers=RSPAMD_MAX_WORKERS) as executor:
        future_to_index = {
            executor.submit(
                evaluate_email,
                job["email_path"],
                job["dataset"],
                job["label"],
                job["message_id"],
                job.get("variant_filename", ""),
                job.get("salting_meta"),
            ): idx
            for idx, job in enumerate(jobs)
        }

        with tqdm(
            total=len(jobs),
            desc=desc,
            unit="mail",
            colour="green",
            file=sys.stdout,
        ) as progress_bar:
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results_by_index[idx] = future.result()
                progress_bar.update(1)

    return [results_by_index[i] for i in range(len(jobs))]


def run_rspamd_evaluation(output_root=None, dataset_split_dir=None):
    """
    Run the complete Rspamd evaluation workflow.

    Args:
        output_root: Root directory for generated evaluation artifacts.
        dataset_split_dir: Directory containing the train/test dataset split.
    """

    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir

    result_dir = output_root / "rspamd_evaluation"
    salted_emails_dir = output_root / "salted_email_generator" / "emails"
    salting_log_csv = output_root / "salted_email_generator" / "salting_log.csv"

    result_csv = result_dir / "rspamd_results.csv"
    paired_result_csv = result_dir / "rspamd_results_paired.csv"

    print_step("Rspamd Evaluation")

    test_spam_dir = dataset_split_dir / "test" / "spam"
    test_ham_dir = dataset_split_dir / "test" / "ham"

    salting_index = load_salting_log(salting_log_csv)
    salted_source_ids = load_salted_source_ids(salting_log_csv)

    # Only keep baseline spam emails for which at least one salted variant exists.
    spam_files = [
        p for p in sorted(test_spam_dir.iterdir())
        if p.is_file() and p.name in salted_source_ids
    ]

    ham_files = [p for p in sorted(test_ham_dir.iterdir()) if p.is_file()]
    salted_files = [p for p in sorted(salted_emails_dir.iterdir()) if p.is_file()]

    print_section("Evaluation dataset")
    print_kv("baseline_spam_paired", len(spam_files))
    print_kv("baseline_ham", len(ham_files))
    print_kv("salted_variants", len(salted_files))
    print_kv("salted_source_emails", len(salted_source_ids))
    print_kv("rspamd_max_workers", RSPAMD_MAX_WORKERS)

    print_section("Scanning emails")

    spam_jobs = [
        {
            "email_path": path,
            "dataset": "baseline",
            "label": "spam",
            "message_id": path.name,
        }
        for path in spam_files
    ]

    ham_jobs = [
        {
            "email_path": path,
            "dataset": "baseline",
            "label": "ham",
            "message_id": path.name,
        }
        for path in ham_files
    ]

    salted_jobs = [
        {
            "email_path": path,
            "dataset": "salted",
            "label": "spam",
            "message_id": salting_index.get(path.name, {}).get("message_id", ""),
            "variant_filename": path.name,
            "salting_meta": salting_index.get(path.name, {}),
        }
        for path in salted_files
    ]

    results = []
    results.extend(scan_batch(spam_jobs, "Baseline spam"))
    results.extend(scan_batch(ham_jobs, "Baseline ham"))
    results.extend(scan_batch(salted_jobs, "Salted spam"))

    result_dir.mkdir(parents=True, exist_ok=True)

    with open(result_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "label",
                "message_id",
                "variant_filename",
                "vocab_type",
                "codepoint",
                "salt_location",
                "n_insert_subject",
                "n_insert_body",
                "spam_flag",
                "score",
                "threshold",
                "action",
                "rule_count",
                "rules",
                "has_bayes",
                "bayes_symbol",
                "bayes_score",
                "raw_output",
                "has_neural",
                "neural_symbol",
                "neural_score",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(results)

    paired_rows = build_paired_results(results)

    with open(paired_result_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "message_id",
                "baseline_score",
                "baseline_spam_flag",
                "baseline_rule_count",
                "baseline_action",
                "n_variants",
                "salted_score_mean",
                "salted_score_min",
                "salted_score_max",
                "salted_rule_count_mean",
                "salted_any_spam",
                "salted_all_spam",
                "salted_any_bypass",
                "salted_all_bypass",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(paired_rows)

    print_section("Output files")
    print_kv("variant_results_csv", result_csv)
    print_kv("paired_results_csv", paired_result_csv)

    print_end("Rspamd Evaluation")