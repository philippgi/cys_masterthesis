#!/usr/bin/env python3
"""
Analyzes the overlap between SpamAssassin Bayes-relevant tokens and the
strict, extended, and broad trigger vocabularies.

A reproducible sample of training spam emails is inspected using SpamAssassin's
Bayes debug output. Bayes-relevant lexical tokens are extracted and compared
against the three trigger vocabulary scopes.
"""

from __future__ import annotations

import csv
import json
import random
import re
import subprocess
from pathlib import Path
from statistics import mean

from config import (
    ANALYSIS_OUTPUT_DIR,
    BAYES_BROAD_TRIGGER_WORDS_PATH,
    BAYES_EXTENDED_TRIGGER_WORDS_PATH,
    BAYES_STRICT_TRIGGER_WORDS_PATH,
    BAYES_TOKEN_VOCAB_DATASET_DIR,
    BAYES_TOKEN_VOCAB_SAMPLE_SIZE,
    BAYES_TOKEN_VOCAB_THRESHOLD,
    RANDOM_SEED,
    SPAMASSASSIN_CONTAINER,
)

from src.utils.console import print_step, print_section, print_kv, print_end


def _load_trigger_word_set(path: Path) -> set[str]:
    """
    Load trigger tokens from a generated vocabulary file.

    Args:
        path (Path): Path to the trigger vocabulary JSON file.

    Returns:
        set[str]: Trigger tokens contained in the vocabulary.
    """

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {entry["token"] for entry in data.get("triggers", []) if entry.get("token")}


def _safe_rate(num: int, denom: int) -> float:
    """
    Calculate a ratio while avoiding division by zero.

    Args:
        num (int): Numerator.
        denom (int): Denominator.

    Returns:
        float: Calculated ratio, or 0.0 if the denominator is zero.
    """

    return num / denom if denom else 0.0


def _is_lexical_token(token: str) -> bool:
    """
    Determine whether a Bayes token represents a lexical word-like token.

    Args:
        token (str): Token extracted from SpamAssassin Bayes output.

    Returns:
        bool: True if the token matches the lexical token pattern.
    """

    return bool(re.fullmatch(r"[a-z]{3,}(?:[,'-][a-z]{2,})*", token))


def _extract_bayes_relevant_tokens(
    email_path: Path,
    bayes_threshold: float,
) -> list[str]:
    """
    Extract Bayes-relevant tokens from SpamAssassin debug output.

    Args:
        email_path (Path): Spam email to inspect.
        bayes_threshold (float): Minimum Bayes token probability to retain.

    Returns:
        list[str]: Unique tokens meeting the configured Bayes threshold.

    Raises:
        RuntimeError: If the SpamAssassin debug command fails.
    """

    cmd = [
        "docker",
        "exec",
        "-i",
        "-u",
        "debian-spamd",
        SPAMASSASSIN_CONTAINER,
        "spamassassin",
        "-t",
        "-D",
        "bayes",
    ]

    with open(email_path, "rb") as f:
        result = subprocess.run(
            cmd,
            stdin=f,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise RuntimeError(
            "SpamAssassin Bayes debug command failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Mail: {email_path}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    debug_output = result.stdout + "\n" + result.stderr

    pattern = re.compile(
        r"dbg:\s+bayes:\s+token\s+'([^']+)'\s+=>\s+([0-9.]+)",
        re.IGNORECASE,
    )

    token_to_prob = {}

    for token, prob_str in pattern.findall(debug_output):
        token = token.strip().lower()
        token = token.strip("'\"")

        try:
            prob = float(prob_str)
        except ValueError:
            continue

        # Retain the highest observed probability for each token above the threshold.
        if prob >= bayes_threshold:
            if token not in token_to_prob or prob > token_to_prob[token]:
                token_to_prob[token] = prob

    return sorted(token_to_prob.keys())


def run_bayes_token_vocab_overlap() -> None:
    """
    Compare SpamAssassin Bayes-relevant tokens with the trigger vocabularies.

    A reproducible sample of training spam emails is analyzed and overlap statistics
    are exported for the strict, extended, and broad vocabulary scopes.
    """

    dataset_split_dir = BAYES_TOKEN_VOCAB_DATASET_DIR
    sample_size = BAYES_TOKEN_VOCAB_SAMPLE_SIZE
    bayes_threshold = BAYES_TOKEN_VOCAB_THRESHOLD

    analysis_dir = ANALYSIS_OUTPUT_DIR
    analysis_dir.mkdir(parents=True, exist_ok=True)

    overlap_csv = analysis_dir / "bayes_token_vocab_overlap.csv"
    overlap_summary_txt = analysis_dir / "bayes_token_vocab_overlap_summary.txt"

    train_spam_dir = dataset_split_dir / "train" / "spam"

    strict_vocab_path = BAYES_STRICT_TRIGGER_WORDS_PATH
    extended_vocab_path = BAYES_EXTENDED_TRIGGER_WORDS_PATH
    broad_vocab_path = BAYES_BROAD_TRIGGER_WORDS_PATH

    if not train_spam_dir.exists():
        raise FileNotFoundError(f"Missing training spam directory: {train_spam_dir}")

    if not strict_vocab_path.exists():
        raise FileNotFoundError(f"Missing strict trigger vocabulary: {strict_vocab_path}")

    if not extended_vocab_path.exists():
        raise FileNotFoundError(f"Missing extended trigger vocabulary: {extended_vocab_path}")

    if not broad_vocab_path.exists():
        raise FileNotFoundError(f"Missing broad trigger vocabulary: {broad_vocab_path}")

    spam_files = sorted([p for p in train_spam_dir.iterdir() if p.is_file()])
    if not spam_files:
        raise ValueError(f"No spam files found in: {train_spam_dir}")

    strict_tokens = _load_trigger_word_set(strict_vocab_path)
    extended_tokens = _load_trigger_word_set(extended_vocab_path)
    broad_tokens = _load_trigger_word_set(broad_vocab_path)

    rng = random.Random(RANDOM_SEED)
    actual_sample_size = min(sample_size, len(spam_files))
    sampled_files = rng.sample(spam_files, actual_sample_size)

    rows = []

    for email_path in sampled_files:
        bayes_tokens = _extract_bayes_relevant_tokens(
            email_path=email_path,
            bayes_threshold=bayes_threshold,
        )

        # Exclude non-lexical Bayes tokens before comparing them with trigger words.
        bayes_lexical_tokens = sorted([t for t in bayes_tokens if _is_lexical_token(t)])

        strict_matches = sorted(set(bayes_lexical_tokens) & strict_tokens)
        extended_matches = sorted(set(bayes_lexical_tokens) & extended_tokens)
        broad_matches = sorted(set(bayes_lexical_tokens) & broad_tokens)

        row = {
            "message_id": email_path.name,
            "n_bayes_tokens": len(bayes_tokens),
            "n_bayes_lexical_tokens": len(bayes_lexical_tokens),

            "n_strict_matches": len(strict_matches),
            "n_extended_matches": len(extended_matches),
            "n_broad_matches": len(broad_matches),

            "strict_matches_of_bayes_lexical_tokens": f"{len(strict_matches)}/{len(bayes_lexical_tokens)}",
            "extended_matches_of_bayes_lexical_tokens": f"{len(extended_matches)}/{len(bayes_lexical_tokens)}",
            "broad_matches_of_bayes_lexical_tokens": f"{len(broad_matches)}/{len(bayes_lexical_tokens)}",

            "strict_match_rate": _safe_rate(len(strict_matches), len(bayes_lexical_tokens)),
            "extended_match_rate": _safe_rate(len(extended_matches), len(bayes_lexical_tokens)),
            "broad_match_rate": _safe_rate(len(broad_matches), len(bayes_lexical_tokens)),

            "bayes_relevant_tokens": " | ".join(repr(t) for t in bayes_tokens),
            "bayes_lexical_tokens": " | ".join(repr(t) for t in bayes_lexical_tokens),
            "strict_matches": " | ".join(repr(t) for t in strict_matches),
            "extended_matches": " | ".join(repr(t) for t in extended_matches),
            "broad_matches": " | ".join(repr(t) for t in broad_matches),
        }
        rows.append(row)

    with open(overlap_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "message_id",
                "n_bayes_tokens",
                "n_bayes_lexical_tokens",
                "n_strict_matches",
                "n_extended_matches",
                "n_broad_matches",
                "strict_matches_of_bayes_lexical_tokens",
                "extended_matches_of_bayes_lexical_tokens",
                "broad_matches_of_bayes_lexical_tokens",
                "strict_match_rate",
                "extended_match_rate",
                "broad_match_rate",
                "bayes_relevant_tokens",
                "bayes_lexical_tokens",
                "strict_matches",
                "extended_matches",
                "broad_matches",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    n_mails_with_bayes_tokens = sum(1 for row in rows if row["n_bayes_tokens"] > 0)
    n_mails_with_bayes_lexical_tokens = sum(1 for row in rows if row["n_bayes_lexical_tokens"] > 0)

    n_mails_with_strict_match = sum(1 for row in rows if row["n_strict_matches"] > 0)
    n_mails_with_extended_match = sum(1 for row in rows if row["n_extended_matches"] > 0)
    n_mails_with_broad_match = sum(1 for row in rows if row["n_broad_matches"] > 0)

    mean_bayes_tokens = mean(row["n_bayes_tokens"] for row in rows) if rows else 0.0
    mean_bayes_lexical_tokens = mean(row["n_bayes_lexical_tokens"] for row in rows) if rows else 0.0

    mean_strict_matches = mean(row["n_strict_matches"] for row in rows) if rows else 0.0
    mean_extended_matches = mean(row["n_extended_matches"] for row in rows) if rows else 0.0
    mean_broad_matches = mean(row["n_broad_matches"] for row in rows) if rows else 0.0

    mean_strict_rate = mean(row["strict_match_rate"] for row in rows) if rows else 0.0
    mean_extended_rate = mean(row["extended_match_rate"] for row in rows) if rows else 0.0
    mean_broad_rate = mean(row["broad_match_rate"] for row in rows) if rows else 0.0

    with open(overlap_summary_txt, "w", encoding="utf-8") as f:
        f.write("Bayes Token / Trigger Vocabulary Overlap\n")
        f.write("=======================================\n\n")
        f.write(f"Training spam directory : {train_spam_dir}\n")
        f.write(f"Strict vocabulary       : {strict_vocab_path}\n")
        f.write(f"Extended vocabulary     : {extended_vocab_path}\n")
        f.write(f"Broad vocabulary        : {broad_vocab_path}\n")
        f.write(f"Requested sample size   : {sample_size}\n")
        f.write(f"Actual sample size      : {actual_sample_size}\n")
        f.write(f"Random seed             : {RANDOM_SEED}\n")
        f.write(f"Bayes threshold         : {bayes_threshold}\n\n")

        f.write("Aggregate summary\n")
        f.write("-----------------\n")
        f.write(f"Mails with Bayes-relevant tokens        : {n_mails_with_bayes_tokens}/{actual_sample_size}\n")
        f.write(f"Mails with lexical Bayes tokens         : {n_mails_with_bayes_lexical_tokens}/{actual_sample_size}\n")
        f.write(f"Mails with strict overlap               : {n_mails_with_strict_match}/{actual_sample_size}\n")
        f.write(f"Mails with extended overlap             : {n_mails_with_extended_match}/{actual_sample_size}\n")
        f.write(f"Mails with broad overlap                : {n_mails_with_broad_match}/{actual_sample_size}\n")
        f.write(f"Mean Bayes-relevant tokens/mail         : {mean_bayes_tokens:.2f}\n")
        f.write(f"Mean lexical Bayes tokens/mail          : {mean_bayes_lexical_tokens:.2f}\n")
        f.write(f"Mean strict matches/mail                : {mean_strict_matches:.2f}\n")
        f.write(f"Mean extended matches/mail              : {mean_extended_matches:.2f}\n")
        f.write(f"Mean broad matches/mail                 : {mean_broad_matches:.2f}\n")
        f.write(f"Mean strict match rate                  : {mean_strict_rate:.6f}\n")
        f.write(f"Mean extended match rate                : {mean_extended_rate:.6f}\n")
        f.write(f"Mean broad match rate                   : {mean_broad_rate:.6f}\n\n")

        f.write("Per-mail overview\n")
        f.write("-----------------\n")
        for row in rows:
            f.write(f"{row['message_id']}:\n")
            f.write(f"  n_bayes_tokens                         : {row['n_bayes_tokens']}\n")
            f.write(f"  n_bayes_lexical_tokens                 : {row['n_bayes_lexical_tokens']}\n")
            f.write(f"  n_strict_matches                       : {row['n_strict_matches']}\n")
            f.write(f"  n_extended_matches                     : {row['n_extended_matches']}\n")
            f.write(f"  n_broad_matches                        : {row['n_broad_matches']}\n")
            f.write(f"  strict_matches_of_bayes_lexical_tokens : {row['strict_matches_of_bayes_lexical_tokens']}\n")
            f.write(f"  extended_matches_of_bayes_lexical_tokens: {row['extended_matches_of_bayes_lexical_tokens']}\n")
            f.write(f"  broad_matches_of_bayes_lexical_tokens  : {row['broad_matches_of_bayes_lexical_tokens']}\n")
            f.write(f"  strict_match_rate                      : {row['strict_match_rate']}\n")
            f.write(f"  extended_match_rate                    : {row['extended_match_rate']}\n")
            f.write(f"  broad_match_rate                       : {row['broad_match_rate']}\n")
            f.write(f"  bayes_relevant_tokens                  : {row['bayes_relevant_tokens']}\n")
            f.write(f"  bayes_lexical_tokens                   : {row['bayes_lexical_tokens']}\n")
            f.write(f"  strict_matches                         : {row['strict_matches']}\n")
            f.write(f"  extended_matches                       : {row['extended_matches']}\n")
            f.write(f"  broad_matches                          : {row['broad_matches']}\n\n")

    print_step("Bayes Token / Vocabulary Overlap")

    print_section("Output files")
    print_kv("overlap_csv", overlap_csv)
    print_kv("overlap_summary_txt", overlap_summary_txt)

    print_end("Bayes Token / Vocabulary Overlap")