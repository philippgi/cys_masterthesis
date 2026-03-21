#!/usr/bin/env python3

"""
Step 4 - Charset Decoding (Unicode Text Representation)

This step converts the decoded byte stream obtained after Content-Transfer-
Decoding into a Unicode string using the character set declared in the MIME
headers.

Scope of this step:
- Transform raw bytes into a Unicode text representation.
- Make individual Unicode code points explicit and observable.
- Do NOT perform Unicode normalization or tokenization at this stage.

This step marks the transition from a byte-level representation to a
character-level (Unicode) representation of the message body.
"""
from src.utils.console import print_section


def step4_charset_decode(text_part, decoded_bytes):
    """
    Decode the byte stream into a Unicode string using the charset declared
    in the MIME headers.

    Args:
        text_part: The MIME part selected in Step 2 ("text/plain" of EmailMessage object).
        decoded_bytes (bytes): Byte sequence obtained after Content-Transfer-Decoding in Step 3.

    Returns:
        text (str): Unicode string representation of the message body.
    """

    # Read the declared charset from the MIME headers.
    # If no charset is declared, UTF-8 is used as a safe default.
    charset = text_part.get_content_charset()
    if charset is None:
        charset = "utf-8"

    print_section("DECLARED CHARSET (effective)")
    print(charset)

    # Decode the byte stream into a Unicode string.
    # This operation reconstructs Unicode code points from the byte sequence.
    text = decoded_bytes.decode(charset)

    print_section("UNICODE STRING (visible rendering)")
    print(text)

    # Explicitly list Unicode code points to make invisible characters observable.
    print_section("UNICODE CODEPOINTS (first 250 characters)")
    codepoints = [hex(ord(c)) for c in text[:250]]
    print(codepoints)

    # Check whether the Zero-Width Space (U+200B) is present in the Unicode text.
    # At this stage, the injected character becomes an explicit element of the character-level representation.
    positions = [i for i, c in enumerate(text) if ord(c) == 0x200B]

    print("\nU+200B positions in decoded text:", positions)

    return text
