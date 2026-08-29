#!/usr/bin/env python3
"""
Computes spam-association scores from spam and ham document frequencies.

Smoothed document-occurrence probabilities are transformed into log odds,
and the difference between spam and ham log odds is used to rank tokens.
"""

from math import log


def logit(p: float) -> float:
    """
    Compute the logit transformation of a probability.

    Args:
        p (float): Probability in the open interval (0, 1).

    Returns:
        float: Log odds of the probability.
    """
    return log(p / (1.0 - p))


def compute_log_odds(df_spam, df_ham, N_spam: int, N_ham: int, ALPHA: float):
    """
    Compute smoothed document-frequency log-odds scores for spam tokens.

    Args:
        df_spam: Spam document-frequency counts.
        df_ham: Ham document-frequency counts.
        N_spam (int): Number of spam documents.
        N_ham (int): Number of ham documents.
        ALPHA (float): Additive smoothing constant.

    Returns:
        dict[str, float]: Spam-vs.-ham log-odds score for each token observed in spam.
    """
    scores = {}

    for token, ds in df_spam.items():
        # Treat tokens absent from ham as having zero ham document frequency.
        dh = df_ham.get(token, 0)

        # Estimate smoothed document-occurrence probabilities for spam and ham.
        ps = (ds + ALPHA) / (N_spam + 2 * ALPHA)
        ph = (dh + ALPHA) / (N_ham + 2 * ALPHA)

        # Use the spam-minus-ham log-odds difference as the association score.
        scores[token] = logit(ps) - logit(ph)

    return scores
