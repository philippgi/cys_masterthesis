#!/usr/bin/env python3
"""
This module orchestrates the salting candidate selection step.

It reads the trigger coverage results from the previous pipeline stage,
applies the configured candidate selection logic, and writes the resulting
candidate and exclusion lists.

The purpose of this step is to determine which spam test emails will be
used in the salting experiment based on the selected salting vocabulary.
"""

import json

from config import OUTPUT_ROOT, SALTING_VOCABULARY
from src.salting_candidate_selection.selector import (
    read_coverage_results,
    select_candidates,
    write_csv,
    build_summary,
    validate_salting_vocabulary,
)


def run_salting_candidate_selection():
    """
    Runs the salting candidate selection step.

    Workflow:
    - Load trigger coverage results from the trigger_coverage module
    - Validate the configured salting vocabulary
    - Select salted candidates according to the configured vocabulary
    - Write candidate and exclusion lists to csv files
    - Write a summary for later documentation in the thesis

    Returns:
        None
    """
    # Get input
    validate_salting_vocabulary(SALTING_VOCABULARY)
    coverage_dir = OUTPUT_ROOT.parent / "trigger_coverage"
    coverage_csv = coverage_dir / "coverage_results.csv"

    if not coverage_csv.exists():
        raise FileNotFoundError(
            f"Missing trigger coverage file: {coverage_csv}"
        )

    # Set output directory
    selection_output_dir = OUTPUT_ROOT.parent / "salting_candidate_selection"
    selection_output_dir.mkdir(parents=True, exist_ok=True)

    # Read per-email trigger coverage statistics
    coverage_rows = read_coverage_results(coverage_csv)

    # Apply selection logic based on the configured salting vocabulary.
    candidates, excluded = select_candidates(
        rows=coverage_rows,
        salting_vocabulary=SALTING_VOCABULARY,
    )

    # Write the selected candidate pool and excluded emails to csv
    write_csv(candidates, selection_output_dir / "salted_candidates.csv")
    write_csv(excluded, selection_output_dir / "excluded_spam.csv")

    # Write summary
    summary = build_summary(
        candidates=candidates,
        excluded=excluded,
        salting_vocabulary=SALTING_VOCABULARY,
    )

    with open(
        selection_output_dir / "selection_summary.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, indent=2)

    print("Salting Candidate Selection:")
    print(f"Salting vocabulary: {SALTING_VOCABULARY}")
    print(f"Spam test emails total: {summary['n_spam_test_total']}")
    print(f"Salted candidates: {summary['n_spam_salted_candidates']}")
    print(f"Excluded spam emails: {summary['n_spam_excluded']}")

    # Error handling
    if summary["n_spam_salted_candidates"] == 0:
        raise ValueError(
            "No salted candidates were selected. "
            "Please check the trigger coverage results and the configured "
            "SALTING_VOCABULARY."
        )