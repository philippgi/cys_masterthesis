#!/usr/bin/env python3

"""
Applies Unicode normalization to the decoded text.

This stage evaluates the four standard Unicode normalization forms
NFC, NFD, NFKC, and NFKD and checks whether U+200B is preserved.
One selected representation is returned for subsequent tokenization.
"""

import unicodedata
from src.utils.console import print_section


def step5_normalize(text, apply_form="NFC"):
    """
    Normalize the Unicode text using the standard normalization forms.

    Args:
        text (str): Unicode text produced by charset decoding in Step 4.
        apply_form (str): Normalization form returned for subsequent processing.

    Returns:
        str: Text normalized using the selected normalization form.
    """

    forms = ["NFC", "NFD", "NFKC", "NFKD"]
    results = {}
    print_section("Show Normalization Forms")

    # Compare all normalization forms to determine whether U+200B is preserved.
    for form in forms:
        norm = unicodedata.normalize(form, text)
        results[form] = norm
        print("\n---- NORMALIZATION", form, "----")

        # Use repr() to make invisible characters such as U+200B observable.
        print("repr:", repr(norm))
        positions = [i for i, c in enumerate(norm) if ord(c) == 0x200B]
        print("U+200B positions:", positions)

    if apply_form not in results:
        print("[error] Unknown normalization form:", apply_form)
        return text

    # Return the selected normalization form for Step 6.
    print("SELECTED NORMALIZED OUTPUT (used for next step):", apply_form)
    return results[apply_form]
