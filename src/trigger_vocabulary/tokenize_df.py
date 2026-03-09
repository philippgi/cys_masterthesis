#!/usr/bin/env python3
"""
This module converts each email into a set of normalized tokens and builds
document-frequency (DF) counts separately for spam and ham.
"""
import re
from typing import Set
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from src.trigger_vocabulary.email_extract import extract_subject_and_text_plain


class PreTokenizationConfig:
    """
    Groups all regex patterns and constants used during pre-tokenization
    cleanup and token extraction.
    """
    # Remove URLs
    URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

    # Strip HTML markup that leaked into text/plain
    HTML_TAG_RE = re.compile(r"<[^>]+>")
    HTML_ENTITY_RE = re.compile(r"&[a-z]+;", re.IGNORECASE)

    # Token definition: lowercase alphabetic tokens, minimum length 3
    TOKEN_RE = re.compile(r"[a-z]{3,}")

    # Explicitly drop common presentational / markup artifacts
    HTML_ARTIFACTS = {
        "nbsp", "font", "bgcolor", "ffffff", "href", "align",
        "arial", "sans", "serif", "helvetica",
    }


def pre_tokenization_cleanup(text: str) -> str:
    """
    Applies the defined pre-tokenization cleanup to raw email text.
    """
    text = PreTokenizationConfig.URL_RE.sub(" ", text)
    text = PreTokenizationConfig.HTML_TAG_RE.sub(" ", text)
    text = PreTokenizationConfig.HTML_ENTITY_RE.sub(" ", text)

    return text


def tokenize_for_df(subject: str, body: str) -> Set[str]:
    """
    Tokenizes an email into a set of normalized tokens.
    Each token is counted at most once per email, as required for document-frequency (DF) statistics.

    Processing steps:
    1) Merge subject and body
    2) Lowercase
    3) Pre-tokenization cleanup
    4) Extract alphabetic tokens (min length 3)
    5) Remove stopwords and known markup artifacts

    Args:
        subject (str): Decoded Subject header.
        body (str): Decoded text/plain body.

    Returns: Set[str]: Unique tokens present in the email.
    """
    # Merge subject and body into a single text stream
    text = f"{subject}\n{body}".lower()

    # Apply cleanup before token extraction
    text = pre_tokenization_cleanup(text)

    # Extract candidate tokens according to the configured token definition
    tokens = set(PreTokenizationConfig.TOKEN_RE.findall(text))

    # Remove common English stopwords
    tokens = {t for t in tokens if t not in ENGLISH_STOP_WORDS}

    # Remove HTML markup/presentation artifacts
    tokens = {t for t in tokens if t not in PreTokenizationConfig.HTML_ARTIFACTS}

    return tokens


def build_df_counts(spam_dir: Path, ham_dir: Path):
    """
    Builds separate document-frequency counters for spam and ham corpora.
    """
    # Document-frequency counters
    df_spam = Counter()
    df_ham = Counter()

    # Number of processed documents per class
    N_spam = 0
    N_ham = 0

    # Process spam corpus
    for p in spam_dir.iterdir():
        # Skip non-regular files
        if not p.is_file():
            continue
        # Extract plain-text representation of the email with helper function
        # defined in 'email_extract.py'
        subj, body = extract_subject_and_text_plain(p)

        # Convert the message into a  token set
        tokens = tokenize_for_df(subj, body)

        # Update DF counts: each token contributes +1 for this document
        df_spam.update(tokens)
        N_spam += 1

    # Process ham corpus (documented in 'spam corpus')
    for p in ham_dir.iterdir():
        if not p.is_file():
            continue
        subj, body = extract_subject_and_text_plain(p)
        tokens = tokenize_for_df(subj, body)
        df_ham.update(tokens)
        N_ham += 1

    return df_spam, df_ham, N_spam, N_ham
