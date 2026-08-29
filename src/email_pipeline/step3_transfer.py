#!/usr/bin/env python3

"""
Applies content-transfer decoding to the selected MIME part.

This stage removes transport encodings such as quoted-printable or base64
and returns the resulting byte sequence. Charset decoding and Unicode
interpretation are deferred to the subsequent stage.
"""

from src.utils.console import print_section


def step3_transfer_decode_part(text_part):
    """
    Decode the Content-Transfer-Encoding of the selected MIME part.

    Args:
        text_part: The text/plain MIME part selected in Step 2.

    Returns:
        bytes | None: The decoded byte sequence, or None if decoding fails.
    """

    # Apply the Content-Transfer-Encoding declared by the MIME part.
    decoded_bytes = text_part.get_payload(decode=True)

    if decoded_bytes is None:
        print("[error] Content-Transfer-Decoding failed or returned None.")
        return None

    print_section("DECODED BYTES (python repr)")
    print(repr(decoded_bytes))

    print_section("DECODED BYTES (hex, first 200 bytes)")
    hex_dump = [hex(b) for b in decoded_bytes[:200]]
    print(hex_dump)

    # Verify that the UTF-8 byte sequence of U+200B survives transfer decoding.
    zwc_bytes = b"\xe2\x80\x8b"
    pos = decoded_bytes.find(zwc_bytes)

    print("\nUTF-8 sequence E2 80 8B found at byte offset:", pos)

    return decoded_bytes
