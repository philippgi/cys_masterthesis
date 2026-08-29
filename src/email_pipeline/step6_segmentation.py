#!/usr/bin/env python3

"""
Tokenizes the normalized Unicode text using two regex-based approximations.

This stage compares an ASCII-only tokenizer with Python's Unicode-aware
regular-expression tokenizer to illustrate how U+200B can affect token
boundaries.
"""

import re

from src.utils.console import print_section


def step6_word_segmentation(text):
    """
    Tokenize the normalized text using ASCII-only and Unicode-aware patterns.

    Args:
        text (str): Normalized Unicode text produced in Step 5.

    Returns:
        tuple[list[str], list[str]]: ASCII-based and Unicode-aware token lists.
    """

    # Lowercase the text to make token comparison case-insensitive.
    text_lower = text.lower()

    # Split on non-ASCII alphanumeric characters to approximate ASCII word boundaries.
    print_section("TOKENIZATION A: ASCII-only [0-9A-Za-z]")
    tokens_ascii = re.split(r"[^0-9a-zA-Z]+", text_lower)

    # Remove empty tokens introduced by consecutive delimiters.
    tokens_ascii = [t for t in tokens_ascii if t]

    for t in tokens_ascii:
        print(repr(t))
    print("\ntoken count:", len(tokens_ascii))

    # Use Python's Unicode-aware \w character class as a second approximation.
    print_section("TOKENIZATION B: Unicode \\w+")
    tokens_unicode = re.findall(r"\w+", text_lower)

    for t in tokens_unicode:
        print(repr(t))
    print("[diagnostic] token count:", len(tokens_unicode))

    return tokens_ascii, tokens_unicode
