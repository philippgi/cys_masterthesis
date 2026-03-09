#!/usr/bin/env python3
"""
This module contains the core logic for trigger coverage analysis.

Its purpose is to determine, for each spam email in the test set,
whether trigger words from the strict and extended trigger vocabularies
occur in the subject and/or body.

In contrast to document-frequency tokenization, repeated token occurrences
are preserved because the coverage analysis must count how often trigger
words appear in each email field.
"""

from collections import Counter
import csv


def tokenize_with_occurrences(text, cleanup_fn, token_regex, html_artifacts):
    """
    Converts a text string into a list of normalized tokens while preserving
    repeated occurrences.

    The function applies the same normalization steps that are used during
    trigger vocabulary construction:
    - lowercase conversion
    - pre-tokenization cleanup
    - regex-based token extraction
    - removal of known HTML artifacts

    Unlike DF-based tokenization, this function does not collapse tokens into
    a set. Repeated trigger words must remain visible for later counting.

    Args:
        text: Raw input text (e.g., email subject or body).
        cleanup_fn: Normalization function applied before token extraction.
        token_regex: Compiled regex pattern defining valid tokens.
        html_artifacts: Set of tokens that should be removed as HTML artifacts.

    Returns:
        A list of normalized tokens including repeated occurrences.
    """
    text = text.lower()
    text = cleanup_fn(text)

    tokens = token_regex.findall(text)
    tokens = [t for t in tokens if t not in html_artifacts]

    return tokens


def count_trigger_occurrences(tokens, trigger_words):
    """
    Counts how many token occurrences belong to the given trigger vocabulary.

    The function first builds token frequencies and then sums the counts of
    all tokens that are contained in the trigger word set.

    Args:
        tokens: List of normalized tokens, possibly with repetitions.
        trigger_words: Set of trigger words to check against.

    Returns:
        The total number of trigger token occurrences in the token list.
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
    can later be distinguished by field. The function evaluates both trigger
    vocabularies:
    - strict trigger vocabulary
    - extended trigger vocabulary

    For each vocabulary, it determines:
    - whether at least one trigger is present in the email
    - how many trigger occurrences appear in the subject
    - how many trigger occurrences appear in the body

    Args:
        subject: Decoded email subject.
        body: Decoded plain-text email body.
        strict_triggers: Set of trigger words from the strict vocabulary.
        extended_triggers: Set of trigger words from the extended vocabulary.
        cleanup_fn: Normalization function applied before token extraction.
        token_regex: Compiled regex pattern defining valid tokens.
        html_artifacts: Set of tokens removed as HTML artifacts.

    Returns:
        A dictionary containing per-email trigger coverage statistics.
    """
    # Tokenize subject and body separately to preserve field-level coverage.
    subject_tokens = tokenize_with_occurrences(
        subject, cleanup_fn, token_regex, html_artifacts
    )

    body_tokens = tokenize_with_occurrences(
        body, cleanup_fn, token_regex, html_artifacts
    )

    # Count strict trigger occurrences in subject and body.
    strict_subject = count_trigger_occurrences(subject_tokens, strict_triggers)
    strict_body = count_trigger_occurrences(body_tokens, strict_triggers)

    # Count extended trigger occurrences in subject and body.
    extended_subject = count_trigger_occurrences(subject_tokens, extended_triggers)
    extended_body = count_trigger_occurrences(body_tokens, extended_triggers)

    return {
        "strict_has_trigger": (strict_subject + strict_body) > 0,
        "extended_has_trigger": (extended_subject + extended_body) > 0,
        "strict_subject_count": strict_subject,
        "strict_body_count": strict_body,
        "extended_subject_count": extended_subject,
        "extended_body_count": extended_body,
    }


def write_csv(results, output_path):
    """
    Writes per-email trigger coverage results to a CSV file.

    Each row represents one analyzed spam email from the test set.
    The CSV output is intended for later evaluation and documentation
    in the thesis.

    Args:
        results: List of dictionaries with per-email coverage statistics.
        output_path: Target path of the CSV output file.

    Returns:
        None
    """
    if not results:
        return

    fieldnames = list(results[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)