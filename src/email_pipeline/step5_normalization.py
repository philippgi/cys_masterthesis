#!/usr/bin/env python3

"""
Step 5 - Unicode Normalization (Canonical Text Representation)

This step applies Unicode normalization to the decoded Unicode text in order
to transform it into a canonical representation. The purpose is to examine
whether Unicode normalization removes, alters, or preserves the injected
zero-width Unicode character (U+200B).

Scope of this step:
- Apply all four standard Unicode normalization forms (NFC, NFD, NFKC, NFKD).
- Observe the effect of normalization on invisible Unicode characters.
- Do NOT perform tokenization or semantic analysis at this stage.

This step operates entirely on Unicode text and does not modify the byte-level representation of the message.
"""

import unicodedata


def step5_normalize(text, apply_form="NFC"):
    """
    Apply Unicode normalization to the decoded Unicode text.

    Args:
        text (str): Unicode string obtained after charset decoding in Step 4.
        apply_form (str): Normalization form to return for subsequent processing
                          (one of: NFC, NFD, NFKC, NFKD).

    Returns:
        normalized_text (str): Unicode text normalized using the selected form.
    """

    # All standard Unicode normalization forms as defined by the Unicode Consortium.
    forms = ["NFC", "NFD", "NFKC", "NFKD"]
    results = {}

    for form in forms:
        # Apply the selected Unicode normalization form.
        # Normalization operates on Unicode code points and does not remove
        # characters unless a canonical or compatibility mapping exists.
        norm = unicodedata.normalize(form, text)
        results[form] = norm

        print("\n---- NORMALIZATION", form, "----")

        # repr() is used to make invisible characters (e.g., U+200B) observable
        print("repr:", repr(norm))

        # Locate positions of the Zero-Width Space (U+200B) after normalization.
        # This verifies whether normalization affects the injected character.
        positions = [i for i, c in enumerate(norm) if ord(c) == 0x200B]
        print("U+200B positions:", positions)

    if apply_form not in results:
        print("[error] Unknown normalization form:", apply_form)
        return text

    # Select one normalized representation for further processing (Step 6)
    print("\n---- SELECTED NORMALIZED OUTPUT (used for next step):", apply_form, "----")
    return results[apply_form]
