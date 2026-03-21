#!/usr/bin/env python3
"""
This module orchestrates the trigger coverage analysis.

It loads the previously constructed trigger vocabularies, iterates over all
spam emails in the test split, extracts subject and body text, and checks if
an email includes trigger words from the strict or extended vocabularies.

The resulting per-email statistics are written to a master CSV file. In
addition, derived compatibility outputs are written for downstream pipeline
steps:
- salted_candidates.csv
- excluded_spam.csv
- selection_summary.json
"""

import json

from config import OUTPUT_ROOT, SALTING_VOCABULARY, DATASET_SPLIT
from src.main_evaluation.trigger_vocabulary.email_extract import extract_subject_and_text_plain
from src.utils.console import print_step, print_section, print_kv, print_end
from src.main_evaluation.trigger_vocabulary.tokenize_df import (
    PreTokenizationConfig,
    pre_tokenization_cleanup,
)
from src.main_evaluation.trigger_coverage.coverage_analyzer import (
    analyze_single_email,
    write_csv,
    write_selection_outputs,
)


def load_trigger_words(json_path):
    """
    Loads trigger words from a trigger vocabulary JSON file.

    Args:
        json_path: Path to the trigger vocabulary JSON file.

    Returns:
        A set containing all trigger tokens from the file.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {entry["token"] for entry in data["triggers"]}


def run_trigger_coverage(output_root=None, dataset_split_dir=None, salting_vocabulary=None, dataset_type: str = "test"):
    """
    Runs trigger coverage analysis for all spam emails in the test set.
    """
    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir
    salting_vocabulary = SALTING_VOCABULARY if salting_vocabulary is None else salting_vocabulary

    spam_dir = dataset_split_dir / dataset_type / "spam"
    coverage_output_dir = output_root / "trigger_coverage"
    coverage_output_dir.mkdir(parents=True, exist_ok=True)

    strict_path = output_root / "trigger_vocabulary" / "trigger_words_strict.json"
    extended_path = output_root / "trigger_vocabulary" / "trigger_words_extended.json"
    broad_path = output_root / "trigger_vocabulary" / "trigger_words_broad.json"

    strict_triggers = load_trigger_words(strict_path)
    extended_triggers = load_trigger_words(extended_path)
    broad_triggers = load_trigger_words(broad_path)

    results = []

    print_step("Trigger Coverage")

    print_section("Input dataset")
    print_kv(f"{dataset_type}_spam_dir", spam_dir)

    for email_path in sorted(spam_dir.iterdir()):
        subject, body = extract_subject_and_text_plain(email_path)

        analysis = analyze_single_email(
            subject=subject,
            body=body,
            strict_triggers=strict_triggers,
            extended_triggers=extended_triggers,
            broad_triggers=broad_triggers,
            cleanup_fn=pre_tokenization_cleanup,
            token_regex=PreTokenizationConfig.TOKEN_RE,
            html_artifacts=PreTokenizationConfig.HTML_ARTIFACTS,
        )

        result = {
            "message_id": email_path.name,
            **analysis,
        }
        results.append(result)

    # Master output
    write_csv(results, coverage_output_dir / "coverage_results.csv")

    # Derived compatibility outputs for downstream steps
    selection_output_dir = output_root / "salting_candidate_selection"
    selection_output_dir.mkdir(parents=True, exist_ok=True)

    summary = write_selection_outputs(
        rows=results,
        output_dir=selection_output_dir,
        salting_vocabulary=salting_vocabulary,
    )

    print_section("Coverage summary")
    print_kv(f"spam_{dataset_type}_emails", len(results))
    print_kv(f"salted_candidates_{salting_vocabulary}", summary["n_spam_salted_candidates"])
    print_kv("excluded_spam", summary["n_spam_excluded"])

    print_end("Trigger Coverage")
