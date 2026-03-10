#!/usr/bin/env python3
"""
Core logic for selecting spam emails that are eligible for the salting
experiment.

The module reads the trigger coverage results and separates the spam test
emails into:
- salted candidates
- excluded emails

Selection is based on the configured salting vocabulary:
- strict: only emails with at least one strict trigger are selected
- extended: only emails with at least one extended trigger are selected
"""

import csv


def read_coverage_results(csv_path):
    """
    Reads the trigger coverage CSV produced by the trigger coverage module.

    The CSV is expected to contain one row per spam test email together with
    field-level trigger coverage statistics.

    Args:
        csv_path: Path to the coverage_results.csv file.

    Returns:
        A list of dictionaries containing the CSV rows.
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return rows


def validate_coverage_rows(rows):
    """
    Validates that the coverage CSV contains the required columns.

    This prevents later pipeline steps from silently using incomplete or
    malformed coverage data.

    Args:
        rows: List of dictionaries read from the coverage CSV.

    Returns:
        None

    Raises:
        ValueError: If the CSV is empty or required columns are missing.
    """
    if not rows:
        raise ValueError("coverage_results.csv is empty.")

    required_columns = {
        "message_id",
        "strict_has_trigger",
        "extended_has_trigger",
    }

    available_columns = set(rows[0].keys())
    missing_columns = required_columns - available_columns

    if missing_columns:
        raise ValueError(
            "coverage_results.csv is missing required columns: "
            f"{sorted(missing_columns)}"
        )


def validate_salting_vocabulary(salting_vocabulary):
    """
    Validates the configured salting vocabulary.

    Args:
        salting_vocabulary: Expected to be 'strict' or 'extended'.

    Returns:
        None

    Raises:
        ValueError: If the vocabulary value is invalid.
    """
    if salting_vocabulary not in {"strict", "extended"}:
        raise ValueError(
            f"Invalid SALTING_VOCABULARY '{salting_vocabulary}'. "
            f"Expected 'strict' or 'extended'."
        )


def to_bool(value):
    """
    Converts a CSV string value to a boolean.

    The trigger coverage CSV stores boolean values as strings such as
    'True' or 'False'. This helper normalizes them into Python booleans.

    Args:
        value: String representation of a boolean value.

    Returns:
        True if the value equals 'true' ignoring case, otherwise False.
    """
    return str(value).strip().lower() == "true"


def select_candidates(rows, salting_vocabulary):
    """
    Splits spam test emails into salted candidates and excluded emails.

    Selection is based on the configured salting vocabulary:
    - 'strict': only emails with at least one strict trigger are selected
    - 'extended': only emails with at least one extended trigger are selected

    Args:
        rows: List of per-email trigger coverage rows.
        salting_vocabulary: Either 'strict' or 'extended'.

    Returns:
        A tuple consisting of:
        - candidates: list of selected email rows
        - excluded: list of excluded email rows
    """
    validate_salting_vocabulary(salting_vocabulary)
    validate_coverage_rows(rows)

    candidates = []
    excluded = []

    for row in rows:
        strict_has_trigger = to_bool(row["strict_has_trigger"])
        extended_has_trigger = to_bool(row["extended_has_trigger"])

        # Determine whether the email belongs to the candidate pool
        if salting_vocabulary == "strict":
            is_candidate = strict_has_trigger
        else:
            is_candidate = extended_has_trigger

        if is_candidate:
            candidates.append(dict(row))
        else:
            excluded.append(dict(row))

    return candidates, excluded


def write_csv(rows, output_path):
    """
    Writes a list of dictionaries to a csv file

    Args:
        rows: List of dictionaries to be written
        output_path: Target CSV path

    Returns:
        None
    """
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(candidates, excluded, salting_vocabulary):
    """
    Builds a summary dictionary for the candidate selection step.

    Args:
        candidates: List of selected spam emails
        excluded: List of excluded spam emails
        salting_vocabulary: Configured salting vocabulary

    Returns:
        A dictionary with aggregated selection statistics
    """
    summary = {
        "salting_vocabulary": salting_vocabulary,
        "n_spam_test_total": len(candidates) + len(excluded),
        "n_spam_salted_candidates": len(candidates),
        "n_spam_excluded": len(excluded),
    }

    return summary
