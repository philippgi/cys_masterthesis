#!/usr/bin/env python3

"""
Decodes the transfer-decoded byte sequence into Unicode text.

The charset declared by the MIME part is used to convert the byte-level
representation into a Unicode string. Unicode normalization and tokenization
are deferred to subsequent stages.
"""

from src.utils.console import print_section


def step4_charset_decode(text_part, decoded_bytes):
    """
    Decode the byte sequence using the charset declared by the MIME part.

    Args:
        text_part: The text/plain MIME part selected in Step 2.
        decoded_bytes (bytes): Byte sequence produced by transfer decoding in Step 3.

    Returns:
        str: The decoded Unicode text.
    """

    # Fall back to UTF-8 if the MIME part does not declare a charset.
    charset = text_part.get_content_charset()
    if charset is None:
        charset = "utf-8"

    print_section("DECLARED CHARSET (effective)")
    print(charset)

    text = decoded_bytes.decode(charset)
    print_section("UNICODE STRING (visible rendering)")
    print(text)

    print_section("UNICODE CODEPOINTS (first 250 characters)")

    # Expose code points explicitly so that invisible characters remain observable.
    codepoints = [hex(ord(c)) for c in text[:250]]
    print(codepoints)

    # Check whether the Zero-Width Space (U+200B) is present in the Unicode text.
    # At this stage, the injected character becomes an explicit element of the character-level representation.
    positions = [i for i, c in enumerate(text) if ord(c) == 0x200B]

    print("\nU+200B positions in decoded text:", positions)

    return text
