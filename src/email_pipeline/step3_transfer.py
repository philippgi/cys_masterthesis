#!/usr/bin/env python3

"""
Step 3 - Content-Transfer Decoding (Byte-Level Representation)

This step applies Content-Transfer-Decoding (CTD) to the selected MIME body ("text/plain")
part. The goal is to reverse transport encodings such as quoted-printable or
base64 and reconstruct the original byte sequence of the message body.

Scope of this step:
- Transform the MIME part payload from its transfer-encoded representation
  into raw bytes.
- Do NOT perform charset decoding or Unicode interpretation at this stage.

The resulting byte sequence represents the message body after MIME
Content-Transfer-Encoding has been removed, but before any character
set decoding is applied.
"""
from src.utils.console import print_section


def step3_transfer_decode_part(text_part):
    """
    Decode the Content-Transfer-Encoding of the selected MIME part ("text/plain")
    Args:
        text_part: The MIME part selected in Step 2 ("text/plain" of EmailMessage object).
    Returns:
        decoded_bytes (bytes): Byte sequence after Content-Transfer-Decoding, or None if decoding fails.
    """

    # Apply Content-Transfer-Decoding as specified by the MIME headers.
    # This reverses encodings such as quoted-printable or base64 and yields bytes.
    decoded_bytes = text_part.get_payload(decode=True)

    if decoded_bytes is None:
        print("[error] Content-Transfer-Decoding failed or returned None.")
        return None

    # Python bytes representation of the decoded payload
    print_section("DECODED BYTES (python repr)")
    print(repr(decoded_bytes))

    # Hexadecimal representation (byte-exact view, truncated for readability)
    print_section("DECODED BYTES (hex, first 200 bytes)")
    hex_dump = [hex(b) for b in decoded_bytes[:200]]
    print(hex_dump)

    # Search for the UTF-8 byte sequence corresponding to U+200B (Zero-Width Space).
    # This verifies whether the injected character survives content-transfer decoding at the byte level.
    zwc_bytes = b"\xe2\x80\x8b"
    pos = decoded_bytes.find(zwc_bytes)

    print("\nUTF-8 sequence E2 80 8B found at byte offset:", pos)

    return decoded_bytes
