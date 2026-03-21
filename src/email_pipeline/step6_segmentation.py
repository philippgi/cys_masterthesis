#!/usr/bin/env python3

"""
Step 6 - Word Segmentation (Regex-Based Approximation)

This step tokenizes the normalized Unicode text into word-like units and
observes whether inserting a zero-width Unicode character (U+200B) alters
token boundaries.

Scope of this step:
- Produce a simplified, regex-based tokenization that is sufficient to
  demonstrate the core effect of zero-width characters on token boundaries.
- Compare two tokenization variants:
  (A) an ASCII-only approximation based on [0-9A-Za-z]
  (B) a Unicode-aware approximation using Python's regex shorthand \\w+

Important note:
- This step does not claim to implement full Unicode text segmentation (e.g.,
  UAX #29). The purpose is to illustrate the representation change that occurs
  when filtering systems rely on token-like units for matching and scoring.
"""

import re

from src.utils.console import print_section


def step6_word_segmentation(text):
    """
    Tokenize normalized Unicode text and inspect the effect of U+200B on
    token boundaries.

    Args:
        text (str): Normalized Unicode string from Step 5.

    Returns:
        tuple[list[str], list[str]]:
            tokens_ascii: Tokens produced by an ASCII-only regex approximation.
            tokens_unicode: Tokens produced by a Unicode-aware regex approximation.
    """

    # Lowercasing is applied to make token comparisons case-insensitive
    text_lower = text.lower()

    # Variant A: ASCII-only tokenization approximation.
    # This splits on any character outside [0-9A-Za-z], producing "word-like" tokens.
    print_section("TOKENIZATION A: ASCII-only [0-9A-Za-z]")
    tokens_ascii = re.split(r"[^0-9a-zA-Z]+", text_lower)

    # Remove empty tokens created by consecutive delimiters
    tokens_ascii = [t for t in tokens_ascii if t]

    for t in tokens_ascii:
        print(repr(t))
    print("\ntoken count:", len(tokens_ascii))

    # Variant B: Unicode-aware tokenization approximation.
    # Pythons "re", \\w matches Unicode word characters by default.
    print_section("TOKENIZATION B: Unicode \\w+")
    tokens_unicode = re.findall(r"\w+", text_lower)

    for t in tokens_unicode:
        print(repr(t))
    print("[diagnostic] token count:", len(tokens_unicode))

    return tokens_ascii, tokens_unicode
