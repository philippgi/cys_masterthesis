#!/usr/bin/env python3
"""
This module checks for each spam email in the test set whether trigger words
from the strict and extended trigger vocabularies occur in the subject and/or
body.

In addition to the raw trigger coverage, the module can also derive candidate
flags for later salting:
- is_candidate_strict
- is_candidate_extended

This makes the trigger_coverage output the central master dataset for the next
pipeline stages.
"""

from collections import Counter
import csv
import json


def tokenize_with_occurrences(text, cleanup_fn, token_regex, html_artifacts):
    """
    Converts a text string into a list of normalized tokens.

    The function applies the same normalization steps that are used during
    trigger vocabulary construction:
    - lowercase conversion
    - pre-tokenization cleanup
    - regex-based token extraction
    - removal of known HTML artifacts

    Args:
        text: Raw input text (e.g., email subject or body)
        cleanup_fn: Normalization function applied before token extraction
        token_regex: Compiled regex pattern defining valid tokens
        html_artifacts: Set of tokens that should be removed as HTML artifacts

    Returns:
        A list of normalized tokens including repeated occurrences
    """
    text = text.lower()
    text = cleanup_fn(text)

    tokens = token_regex.findall(text)
    tokens = [t for t in tokens if t not in html_artifacts]

    return tokens


def count_trigger_occurrences(tokens, trigger_words):
    """
    Counts how many token occurrences belong to the given trigger vocabulary.

    Args:
        tokens: List of normalized tokens, possibly with repetitions
        trigger_words: Set of trigger words to check against

    Returns:
        The total number of trigger token occurrences in the token list
    """
    counter = Counter(tokens)
    return sum(count for token, count in counter.items() if token in trigger_words)


def analyze_single_email(
    subject,
    body,
    strict_triggers,
    extended_triggers,
    cleanup_fn,
    token_regex,
    html_artifacts,
):
    """
    Analyzes trigger coverage for a single email.

    The subject and body are tokenized separately so that trigger occurrences
    can later be distinguished by field.

    Returns:
        A dictionary containing per-email trigger coverage statistics
    """
    subject_tokens = tokenize_with_occurrences(
        subject, cleanup_fn, token_regex, html_artifacts
    )
    body_tokens = tokenize_with_occurrences(
        body, cleanup_fn, token_regex, html_artifacts
    )

    strict_subject = count_trigger_occurrences(subject_tokens, strict_triggers)
    strict_body = count_trigger_occurrences(body_tokens, strict_triggers)

    extended_subject = count_trigger_occurrences(subject_tokens, extended_triggers)
    extended_body = count_trigger_occurrences(body_tokens, extended_triggers)

    strict_has_trigger = (strict_subject + strict_body) > 0
    extended_has_trigger = (extended_subject + extended_body) > 0

    return {
        "strict_has_trigger": strict_has_trigger,
        "extended_has_trigger": extended_has_trigger,
        "strict_subject_count": strict_subject,
        "strict_body_count": strict_body,
        "extended_subject_count": extended_subject,
        "extended_body_count": extended_body,
        "is_candidate_strict": strict_has_trigger,
        "is_candidate_extended": extended_has_trigger,
    }


def validate_salting_vocabulary(salting_vocabulary):
    """
    Validates the configured salting vocabulary.
    """
    if salting_vocabulary not in {"strict", "extended"}:
        raise ValueError(
            f"Invalid SALTING_VOCABULARY '{salting_vocabulary}'. "
            f"Expected 'strict' or 'extended'."
        )


def select_candidates_from_coverage(rows, salting_vocabulary):
    """
    Splits the master coverage rows into salted candidates and excluded rows.

    This is now derived directly from the trigger_coverage master output.
    """
    validate_salting_vocabulary(salting_vocabulary)

    candidates = []
    excluded = []

    for row in rows:
        if salting_vocabulary == "strict":
            is_candidate = bool(row["is_candidate_strict"])
        else:
            is_candidate = bool(row["is_candidate_extended"])

        if is_candidate:
            candidates.append(dict(row))
        else:
            excluded.append(dict(row))

    return candidates, excluded


def build_selection_summary(candidates, excluded, salting_vocabulary):
    """
    Builds a compact summary for later documentation.
    """
    validate_salting_vocabulary(salting_vocabulary)

    return {
        "salting_vocabulary": salting_vocabulary,
        "n_spam_test_total": len(candidates) + len(excluded),
        "n_spam_salted_candidates": len(candidates),
        "n_spam_excluded": len(excluded),
    }


def write_csv(results, output_path):
    """
    Writes rows to a CSV file.
    """
    if not results:
        return

    fieldnames = list(results[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def write_selection_outputs(rows, output_dir, salting_vocabulary):
    """
    Writes compatibility outputs for downstream pipeline steps.

    Even though trigger_coverage is now the place where candidate eligibility
    is derived, this helper still writes the historical files expected by later
    modules:
    - salted_candidates.csv
    - excluded_spam.csv
    - selection_summary.json
    """
    candidates, excluded = select_candidates_from_coverage(
        rows=rows,
        salting_vocabulary=salting_vocabulary,
    )

    write_csv(candidates, output_dir / "salted_candidates.csv")
    write_csv(excluded, output_dir / "excluded_spam.csv")

    summary = build_selection_summary(
        candidates=candidates,
        excluded=excluded,
        salting_vocabulary=salting_vocabulary,
    )

    with open(output_dir / "selection_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary