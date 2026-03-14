#!/usr/bin/env python3
"""
Rspamd evaluation runner.

This module evaluates the paired unsalted baseline spam test set
(data/datasets/split/test/spam), the full ham test set
(data/datasets/split/test/ham), and the salted spam variants
(data/output/salted_email_generator/emails) with Rspamd.

Important evaluation logic:
- Baseline ham: all ham test emails
- Baseline spam: only original spam emails for which at least one salted
  variant was actually generated
- Salted spam: all generated salted variants

For each scanned email, the module extracts:
    - spam classification
    - score
    - threshold
    - action
    - triggered symbols

For salted variants, the module also joins metadata from the salting log, such as:
    - vocabulary type
    - used Unicode code point
    - insertion counts in subject and body

Output files:
- rspamd_results.csv
    Variant-level results (one row per scanned email / salted variant)
- rspamd_results_paired.csv
    Original-level paired results (one row per original spam email with
    aggregated salted statistics)
"""

import csv
import json
import http.client
import sys

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
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

# Tune this if needed. Good first values: 4 or 8.
RSPAMD_MAX_WORKERS = 2


def load_salting_log(csv_path: Path) -> dict[str, dict[str, str]]:
    """
    Loads the salting log and indexes it by variant filename.
    """
    if not csv_path.exists():
        return {}

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["variant_filename"]: row for row in reader}


def load_salted_source_ids(csv_path: Path) -> set[str]:
    """
    Loads all original message_ids for which at least one salted variant
    was actually generated.
    """
    if not csv_path.exists():
        return set()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["message_id"] for row in reader if row.get("message_id")}


def derive_salt_location(n_insert_subject, n_insert_body) -> str:
    """
    Derives the location label based on insertion.
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


def run_rspamd_scan(email_path: Path) -> dict:
    """
    Sends one raw RFC 5322 email to the Rspamd normal worker via HTTP
    and parses the JSON response.
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

    score = data.get("score")
    thresholds = data.get("thresholds", {}) or {}
    threshold = thresholds.get("add header")
    action = data.get("action", "")

    spam_flag = action in {"add header", "reject", "soft reject"}

    symbols_dict = data.get("symbols", {}) or {}
    symbol_names = sorted(symbols_dict.keys())

    return {
        "spam_flag": spam_flag,
        "score": score,
        "threshold": threshold,
        "action": action,
        "rule_count": len(symbol_names),
        "rules": "|".join(symbol_names),
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
    Runs Rspamd on one email and returns a result row.
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
        "raw_output": scan["raw_output"],
    }


def build_paired_results(rows: list[dict]) -> list[dict]:
    """
    Builds one paired/original-level result row per original spam email.
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
    Scans one batch of emails in parallel and returns result rows
    in the original job order.
    """
    results_by_index = {}

    with ThreadPoolExecutor(max_workers=RSPAMD_MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                evaluate_email,
                job["email_path"],
                job["dataset"],
                job["label"],
                job["message_id"],
                job.get("variant_filename", ""),
                job.get("salting_meta"),
            )
            for job in jobs
        ]

        for idx, future in enumerate(
            tqdm(
                futures,
                desc=desc,
                unit="mail",
                colour="green",
                file=sys.stdout,
            )
        ):
            results_by_index[idx] = future.result()

    return [results_by_index[i] for i in range(len(jobs))]


def run_rspamd_evaluation(output_root=None, dataset_split_dir=None):
    """
    Main entry point for the Rspamd evaluation.
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
                "raw_output",
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