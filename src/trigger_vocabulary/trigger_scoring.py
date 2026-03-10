#!/usr/bin/env python3
"""
This module implements the statistical core used to derive spam-indicative
trigger vocabulary words from document-frequency statistics.
"""

from math import log


def logit(p: float) -> float:
    """
    Computes the logit transform of a probability.

    Args:
        p (float): Probability value in (0, 1).

    Returns:
        float: log(p / (1 - p))
    """
    return log(p / (1.0 - p))


def compute_log_odds(df_spam, df_ham, N_spam: int, N_ham: int, ALPHA: float):
    """
    Computes DF-based log-odds scores for all tokens observed in spam.

    For each token, the score reflects how much more likely the token
    is to appear in spam documents than in ham documents, using
    smoothed DF-based rates.

    Args:
        df_spam (Counter): Document-frequency counts for spam.
        df_ham (Counter): Document-frequency counts for ham.
        N_spam (int): Number of spam documents.
        N_ham (int): Number of ham documents.
        ALPHA (float): Additive smoothing constant.

    Returns:
        dict[str, float]: token -> log-odds score (spam vs. ham)
    """
    scores = {}

    for token, ds in df_spam.items():
        # Ham DF defaults to zero if token never appears in ham
        dh = df_ham.get(token, 0)

        # Smoothed DF-based occurrence probabilities
        ps = (ds + ALPHA) / (N_spam + 2 * ALPHA)
        ph = (dh + ALPHA) / (N_ham + 2 * ALPHA)

        # Log-odds difference between spam and ham
        scores[token] = logit(ps) - logit(ph)

    return scores
