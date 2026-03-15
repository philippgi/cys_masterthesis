#!/usr/bin/env python3
"""
This module orchestrates the build of a trigger vocabulary
"""

import json
from math import ceil

from config import DATASET_SPLIT, OUTPUT_ROOT, MIN_DF_SPAM, MIN_DF_SPAM_PERCENTAGE, ALPHA
from src.main_evaluation.trigger_vocabulary.tokenize_df import build_df_counts
from src.main_evaluation.trigger_vocabulary.trigger_scoring import compute_log_odds
from src.utils.console import print_step, print_section, print_kv, print_end


def run_trigger_vocabulary(output_root=None, dataset_split_dir=None):

    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir

    output_dir = output_root / "trigger_vocabulary"
    output_dir.mkdir(parents=True, exist_ok=True)

    print_step("Trigger Vocabulary Creation")

    # Build DF counts
    df_spam, df_ham, N_spam, N_ham = build_df_counts(
        dataset_split_dir / "train" / "spam",
        dataset_split_dir / "train" / "ham",
    )

    min_df_spam = max(MIN_DF_SPAM, ceil(MIN_DF_SPAM_PERCENTAGE * N_spam))

    scores = compute_log_odds(df_spam, df_ham, N_spam, N_ham, ALPHA)

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

    candidates.sort(
        key=lambda x: (x["score"], x["spam_df"], x["token"]),
        reverse=True,
    )

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

    print_section("Trigger vocabulary statistics")

    for k, v in stats.items():

        if isinstance(v, float):
            print_kv(k, f"{v:.6f}")
        else:
            print_kv(k, v)

    with open(output_dir / "trigger_vocabulary_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    strict_threshold = 3.0
    extended_threshold = 2.5
    broad_threshold = 1.5

    strict = [c for c in candidates if c["score"] >= strict_threshold]
    extended = [c for c in candidates if c["score"] >= extended_threshold]
    broad = [c for c in candidates if c["score"] >= broad_threshold]

    metadata = {
        "alpha": ALPHA,
        "min_df_spam": min_df_spam,
        "N_spam": N_spam,
        "N_ham": N_ham,
        "strict_threshold": strict_threshold,
        "extended_threshold": extended_threshold,
        "broad_threshold": broad_threshold,
        "token_definition": stats["token_definition"],
    }

    with open(output_dir / "trigger_words_strict.json", "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "triggers": strict}, f, indent=2)

    with open(output_dir / "trigger_words_extended.json", "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "triggers": extended}, f, indent=2)

    with open(output_dir / "trigger_words_broad.json", "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "triggers": broad}, f, indent=2)

    print_end("Trigger Vocabulary Creation")
