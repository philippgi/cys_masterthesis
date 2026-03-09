#!/usr/bin/env python3
"""
This script builds a trigger_vocabulary vocabulary from a labeled spam/ham email corpus.

It assumes that:
- token extraction and normalization are defined in 'email_extract.py' and 'tokenize_df.py'
- each token appears at most once per document (DF model)
"""

import json
from pathlib import Path
from math import ceil

from config import DATASET_SPLIT, OUTPUT_DIR, MIN_DF_SPAM, MIN_DF_SPAM_PERCENTAGE, ALPHA
from src.trigger_vocabulary.tokenize_df import build_df_counts
from src.trigger_vocabulary.trigger_scoring import compute_log_odds


def run_trigger_vocabulary():
    """
    Orchestrates trigger_vocabulary vocabulary construction.

    Steps:
    1) Load DF statistics from training corpus
    2) Compute log-odds scores
    3) Filter and rank candidate tokens
    4) Persist statistics and trigger_vocabulary vocabularies
    """

    print("--> Starting Trigger-Vocabulary creation <--")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Build DF counts from training corpus
    df_spam, df_ham, N_spam, N_ham = build_df_counts(
        DATASET_SPLIT / "train" / "spam",
        DATASET_SPLIT / "train" / "ham",
    )

    # Minimum spam DF threshold:
    # Defined in config

    min_df_spam = max(MIN_DF_SPAM, ceil(MIN_DF_SPAM_PERCENTAGE * N_spam))

    # 2) Compute log-odds scores
    scores = compute_log_odds(df_spam, df_ham, N_spam, N_ham, ALPHA)

    # 3) Build candidate list
    candidates = [
        {
            "token": tok,
            "score": scores[tok],
            "spam_df": df_spam[tok],
            "ham_df": df_ham.get(tok, 0),
            "spam_rate": df_spam[tok] / N_spam,
            "ham_rate": df_ham.get(tok, 0) / N_ham,
        }
        for tok in df_spam
        if df_spam[tok] >= min_df_spam
    ]

    # Deterministic ranking:
    # 1) higher log-odds score
    # 2) higher spam DF
    # 3) lexicographic token order
    candidates.sort(
        key=lambda x: (x["score"], x["spam_df"], x["token"]),
        reverse=True,
    )

    # 4) Statistics for documentation
    stats = {
        "N_spam": N_spam,
        "N_ham": N_ham,
        "alpha": ALPHA,
        "min_df_spam": min_df_spam,
        "total_candidates": len(candidates),
        "count_score_ge_3_0": sum(1 for c in candidates if c["score"] >= 3.0),
        "count_score_ge_2_5": sum(1 for c in candidates if c["score"] >= 2.5),
        "count_score_ge_2_0": sum(1 for c in candidates if c["score"] >= 2.0),
        "score_at_50": candidates[49]["score"] if len(candidates) >= 50 else None,
        "score_at_100": candidates[99]["score"] if len(candidates) >= 100 else None,
        "score_at_200": candidates[199]["score"] if len(candidates) >= 200 else None,
        "score_at_500": candidates[499]["score"] if len(candidates) >= 500 else None,
        "token_definition": (
            "lowercase, alphabetic tokens >=3 chars, URLs removed, "
            "English stopwords removed, HTML tags/entities stripped, "
            "common HTML artifacts removed"
        ),
    }

    print("\nTrigger Vocabulary Statistics:")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"{k:25s}: {v:.6f}")
        else:
            print(f"{k:25s}: {v}")
    print()

    with open(OUTPUT_DIR / "trigger_vocabulary_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # 5) Build trigger_vocabulary vocabularies
    strict_threshold = 3.0
    extended_threshold = 2.5

    strict = [c for c in candidates if c["score"] >= strict_threshold]
    extended = [c for c in candidates if c["score"] >= extended_threshold]

    metadata = {
        "alpha": ALPHA,
        "min_df_spam": min_df_spam,
        "N_spam": N_spam,
        "N_ham": N_ham,
        "strict_threshold": strict_threshold,
        "extended_threshold": extended_threshold,
        "token_definition": stats["token_definition"],
    }

    with open(OUTPUT_DIR / "trigger_words_strict.json", "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "triggers": strict}, f, indent=2)

    with open(OUTPUT_DIR / "trigger_words_extended.json", "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "triggers": extended}, f, indent=2)

    # 6) Optional preview
    top_n_preview = 30
    print(f"Top {top_n_preview} tokens (preview):")
    for c in candidates[:top_n_preview]:
        spam_pct = round(100 * c["spam_rate"])
        ham_pct = round(100 * c["ham_rate"])
        print(
            f'{c["token"]:20s} score={c["score"]:8.3f}  '
            f'spam_df={c["spam_df"]:4d} ({spam_pct:3d} %)  '
            f'ham_df={c["ham_df"]:4d} ({ham_pct:3d} %)'
        )

    print()
    print("--> Trigger-Vocabulary completed <--")
