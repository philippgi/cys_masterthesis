#!/usr/bin/env python3
"""
Analyzes trigger-word coverage for spam emails.

Subject and body content are tokenized using the same normalization logic as
trigger-vocabulary construction. Coverage is evaluated separately for the
strict, extended, and broad vocabularies and is used to derive salting
candidate eligibility.
"""

from collections import Counter
import csv
import json


def tokenize_with_occurrences(text, cleanup_fn, token_regex, html_artifacts):
    """
    Tokenize text using the same normalization pipeline as vocabulary construction.

    Args:
        text (str): Subject or body text.
        cleanup_fn: Pre-tokenization normalization function.
        token_regex: Compiled token extraction pattern.
        html_artifacts: Tokens excluded as known HTML artifacts.

    Returns:
        list[str]: Normalized tokens including repeated occurrences.
    """

    # Reuse the vocabulary-construction normalization to keep coverage matching consistent.
    text = text.lower()
    text = cleanup_fn(text)

    tokens = token_regex.findall(text)
    tokens = [t for t in tokens if t not in html_artifacts]

    return tokens


def count_trigger_occurrences(tokens, trigger_words):
    """
    Count occurrences of vocabulary trigger tokens.

    Args:
        tokens (list[str]): Normalized tokens including repetitions.
        trigger_words: Trigger vocabulary.

    Returns:
        int: Total number of matching token occurrences.
    """

    counter = Counter(tokens)
    return sum(count for token, count in counter.items() if token in trigger_words)


def analyze_single_email(
    subject,
    body,
    strict_triggers,
    extended_triggers,
    broad_triggers,
    cleanup_fn,
    token_regex,
    html_artifacts,
):
    """
    Analyze trigger coverage for one email.

    Subject and body are evaluated separately for all vocabulary scopes.

    Args:
        subject (str): Decoded Subject text.
        body (str): Decoded body text.
        strict_triggers: Strict trigger vocabulary.
        extended_triggers: Extended trigger vocabulary.
        broad_triggers: Broad trigger vocabulary.
        cleanup_fn: Pre-tokenization normalization function.
        token_regex: Compiled token extraction pattern.
        html_artifacts: Tokens excluded as known HTML artifacts.

    Returns:
        dict: Trigger counts, coverage flags, and candidate flags for all scopes.
    """

    # Analyze Subject and body separately so coverage can be attributed to each field.
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

    broad_subject = count_trigger_occurrences(subject_tokens, broad_triggers)
    broad_body = count_trigger_occurrences(body_tokens, broad_triggers)

    # An email is covered by a scope if at least one trigger occurs in Subject or body.
    strict_has_trigger = (strict_subject + strict_body) > 0
    extended_has_trigger = (extended_subject + extended_body) > 0
    broad_has_trigger = (broad_subject + broad_body) > 0

    return {
        "strict_has_trigger": strict_has_trigger,
        "extended_has_trigger": extended_has_trigger,
        "broad_has_trigger": broad_has_trigger,
        "strict_subject_count": strict_subject,
        "strict_body_count": strict_body,
        "extended_subject_count": extended_subject,
        "extended_body_count": extended_body,
        "broad_subject_count": broad_subject,
        "broad_body_count": broad_body,
        "is_candidate_strict": strict_has_trigger,
        "is_candidate_extended": extended_has_trigger,
        "is_candidate_broad": broad_has_trigger,
    }


def validate_salting_vocabulary(salting_vocabulary):
    """
    Validate the selected trigger vocabulary scope.

    Args:
        salting_vocabulary (str): Vocabulary scope to validate.

    Raises:
        ValueError: If the scope is not strict, extended, or broad.
    """

    if salting_vocabulary not in {"strict", "extended", "broad"}:
        raise ValueError(
            f"Invalid SALTING_VOCABULARY '{salting_vocabulary}'. "
            f"Expected 'strict', 'extended', or 'broad'."
        )


def select_candidates_from_coverage(rows, salting_vocabulary):
    """
    Select salting candidates from trigger-coverage results.

    Args:
        rows: Per-email coverage records.
        salting_vocabulary (str): Vocabulary scope used for candidate selection.

    Returns:
        tuple[list, list]: Eligible candidate rows and excluded rows.
    """

    validate_salting_vocabulary(salting_vocabulary)

    candidates = []
    excluded = []

    # Candidate eligibility is determined solely by coverage in the selected vocabulary scope.
    for row in rows:
        if salting_vocabulary == "strict":
            is_candidate = bool(row["is_candidate_strict"])
        elif salting_vocabulary == "extended":
            is_candidate = bool(row["is_candidate_extended"])
        else:
            is_candidate = bool(row["is_candidate_broad"])

        if is_candidate:
            candidates.append(row)
        else:
            excluded.append(row)

    return candidates, excluded


def build_selection_summary(candidates, excluded, salting_vocabulary):
    """
    Build summary counts for salting candidate selection.

    Args:
        candidates: Emails eligible for salting.
        excluded: Emails without trigger coverage in the selected scope.
        salting_vocabulary (str): Vocabulary scope used for selection.

    Returns:
        dict: Candidate-selection summary.
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
    Write result rows to a CSV file.

    Args:
        results: Rows to export.
        output_path: Destination CSV path.
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
    Write candidate-selection artifacts used by downstream pipeline stages.

    Args:
        rows: Trigger-coverage records.
        output_dir: Destination directory.
        salting_vocabulary (str): Vocabulary scope used for candidate selection.

    Returns:
        dict: Candidate-selection summary.
    """

    # Derive downstream salting candidates directly from the coverage results.
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