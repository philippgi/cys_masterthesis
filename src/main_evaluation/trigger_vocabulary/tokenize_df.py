#!/usr/bin/env python3
"""
Builds document-frequency statistics for spam and ham training emails.

Each email is converted into a set of normalized tokens so that every token
contributes at most once per message to the document-frequency counts.
"""

import re
from typing import Set
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from src.main_evaluation.trigger_vocabulary.email_extract import extract_subject_and_text_plain


class PreTokenizationConfig:
    """
    Defines tokenization patterns and exclusions used during vocabulary construction.
    """

    # Remove URLs before token extraction.
    URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

    # Remove HTML markup and entities that leaked into text/plain content.
    HTML_TAG_RE = re.compile(r"<[^>]+>")
    HTML_ENTITY_RE = re.compile(r"&[a-z]+;", re.IGNORECASE)

    # Define lowercase alphabetic tokens with a minimum length of three characters.
    TOKEN_RE = re.compile(r"[a-z]{3,}")

    # Exclude common markup and presentation artifacts.
    HTML_ARTIFACTS = {
        "nbsp", "font", "bgcolor", "ffffff", "href", "align",
        "arial", "sans", "serif", "helvetica",
    }


def pre_tokenization_cleanup(text: str) -> str:
    """
    Remove URLs and HTML-related artifacts before token extraction.

    Args:
        text (str): Raw normalized email text.

    Returns:
        str: Cleaned text.
    """

    text = PreTokenizationConfig.URL_RE.sub(" ", text)
    text = PreTokenizationConfig.HTML_TAG_RE.sub(" ", text)
    text = PreTokenizationConfig.HTML_ENTITY_RE.sub(" ", text)

    return text


def tokenize_for_df(subject: str, body: str) -> Set[str]:
    """
    Convert an email into unique normalized tokens for document-frequency counting.

    Args:
        subject (str): Decoded Subject text.
        body (str): Decoded text/plain body.

    Returns:
        set[str]: Unique tokens present in the email.
    """

    # Treat Subject and body as one document for vocabulary construction.
    text = f"{subject}\n{body}".lower()

    # Apply cleanup before token extraction
    text = pre_tokenization_cleanup(text)

    # Use a set so each token contributes at most once per email to document frequency.
    tokens = set(PreTokenizationConfig.TOKEN_RE.findall(text))

    # Remove common English stopwords and known markup artifacts.
    tokens = {t for t in tokens if t not in ENGLISH_STOP_WORDS}
    tokens = {t for t in tokens if t not in PreTokenizationConfig.HTML_ARTIFACTS}

    return tokens


def build_df_counts(spam_dir: Path, ham_dir: Path):
    """
    Build separate document-frequency counts for spam and ham training emails.

    Args:
        spam_dir (Path): Directory containing spam training emails.
        ham_dir (Path): Directory containing ham training emails.

    Returns:
        tuple: Spam and ham document-frequency counters and document counts.
    """

    df_spam = Counter()
    df_ham = Counter()

    N_spam = 0
    N_ham = 0

    # Build spam document frequencies from one token set per message.
    for p in spam_dir.iterdir():
        if not p.is_file():
            continue

        # Extract plain-text representation of the email with helper function
        # defined in 'email_extract.py'
        subj, body = extract_subject_and_text_plain(p)

        # Convert the message into a token set
        tokens = tokenize_for_df(subj, body)

        # Update DF counts, each token contributes +1 for this document
        df_spam.update(tokens)
        N_spam += 1

    # Repeat the same document-frequency calculation for ham.
    for p in ham_dir.iterdir():
        if not p.is_file():
            continue
        subj, body = extract_subject_and_text_plain(p)
        tokens = tokenize_for_df(subj, body)
        df_ham.update(tokens)
        N_ham += 1

    return df_spam, df_ham, N_spam, N_ham
