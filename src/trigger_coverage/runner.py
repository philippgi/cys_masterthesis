#!/usr/bin/env python3
"""
This module orchestrates the trigger coverage analysis.

It loads the previously constructed trigger vocabularies, iterates over all
spam emails in the test split, extracts subject and body text, and applies
the coverage analysis to each email.

The resulting per-email statistics are written to a CSV file. In addition,
the module prints a short summary showing how many spam test emails contain
at least one strict or extended trigger word.
"""

import json
from pathlib import Path

from config import DATASET_SPLIT, OUTPUT_DIR

from src.trigger_vocabulary.email_extract import extract_subject_and_text_plain
from src.trigger_vocabulary.tokenize_df import (
    PreTokenizationConfig,
    pre_tokenization_cleanup,
)
from src.trigger_coverage.coverage_analyzer import analyze_single_email, write_csv


def load_trigger_words(json_path):
    """
    Loads trigger words from a JSON vocabulary file.

    The expected JSON structure is:
    {
        "triggers": [
            {"token": "...", "score": ...},
            ...
        ]
    }

    Only the token strings are required for coverage analysis, therefore the
    function returns them as a set.

    Args:
        json_path: Path to the trigger vocabulary JSON file.

    Returns:
        A set containing all trigger tokens from the file.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {entry["token"] for entry in data["triggers"]}


def run_trigger_coverage_analysis():
    """
    Runs trigger coverage analysis for all spam emails in the test set.

    Workflow:
    1. Locate the spam portion of the test split.
    2. Load strict and extended trigger vocabularies.
    3. Extract subject and plain-text body from each email.
    4. Analyze trigger coverage per email.
    5. Save the results as CSV.
    6. Print a compact summary for documentation purposes.

    The analysis uses the same normalization settings as the trigger
    vocabulary construction step in order to keep the methodology
    consistent across both phases.

    Returns:
        None
    """
    # Directory containing the spam emails of the test split.
    test_spam_dir = DATASET_SPLIT / "test" / "spam"

    # Output directory for trigger coverage artefacts.
    coverage_output_dir = OUTPUT_DIR.parent / "trigger_coverage"
    coverage_output_dir.mkdir(parents=True, exist_ok=True)

    # Paths to the previously generated trigger vocabularies.
    strict_path = OUTPUT_DIR / "trigger_words_strict.json"
    extended_path = OUTPUT_DIR / "trigger_words_extended.json"

    # Load trigger vocabularies as token sets.
    strict_triggers = load_trigger_words(strict_path)
    extended_triggers = load_trigger_words(extended_path)

    results = []

    # Analyze each spam email in the test set individually.
    for email_path in sorted(test_spam_dir.iterdir()):
        subject, body = extract_subject_and_text_plain(email_path)

        result = analyze_single_email(
            subject,
            body,
            strict_triggers,
            extended_triggers,
            pre_tokenization_cleanup,
            PreTokenizationConfig.TOKEN_RE,
            PreTokenizationConfig.HTML_ARTIFACTS,
        )

        # Store the file name as message identifier for later traceability.
        result["message_id"] = email_path.name
        results.append(result)

    # Write detailed per-email coverage results to CSV.
    write_csv(
        results,
        coverage_output_dir / "coverage_results.csv",
    )

    # Aggregate a minimal summary for quick inspection in the terminal.
    total = len(results)
    with_strict = sum(1 for r in results if r["strict_has_trigger"])
    with_extended = sum(1 for r in results if r["extended_has_trigger"])

    print("Trigger Coverage Analysis")
    print("-------------------------")
    print(f"Spam test emails: {total}")
    print(f"With strict trigger: {with_strict}")
    print(f"With extended trigger: {with_extended}")