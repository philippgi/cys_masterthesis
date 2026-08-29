#!/usr/bin/env python3

"""
Parses the RFC 5322 and MIME structure of the email message.

This stage converts the raw byte stream into a structured message object,
inspects its MIME structure, and selects the relevant text/plain part.
Content-transfer and charset decoding are deferred to subsequent stages.
"""

from email import policy
from email.parser import BytesParser

from src.utils.console import print_section


def step2_parse_mime(raw_bytes):
    """
    Parse the raw message and select the relevant text/plain MIME part.

    Args:
        raw_bytes (bytes): Serialized RFC 5322 message.

    Returns:
        tuple: Parsed message object and selected text/plain part, or None
        if no matching part is available.
    """

    # Parse the serialized message without decoding the body payload.
    msg = BytesParser(policy=policy.compat32).parsebytes(raw_bytes)

    # Top-level headers as interpreted by the parser
    print_section("HEADERS (top-level)")
    for key, value in msg.items():
        print(f"{key}: {value}")

    # MIME structure: single-part vs multipart, and part enumeration
    print_section("MIME STRUCTURE")
    if msg.is_multipart():
        print("Multipart email:")
        for part in msg.walk():
            print(
                "-",
                part.get_content_type(),
                "(disposition:",
                part.get_content_disposition(),
                ")",
            )
    else:
        print("Not multipart.")
        print("Content-Type:", msg.get_content_type())

    # Use the message itself for single-part emails; otherwise select the first text/plain part.
    if not msg.is_multipart():
        text_part = msg
    else:
        text_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                text_part = part
                break

    if text_part is None:
        print("\n[error] No text/plain part found.")
        return msg, None

    # Log metadata of the selected part (relevant for Steps 3-4)
    print_section("SELECTED PART")
    print("Content-Type:", text_part.get_content_type())
    print("Charset:", text_part.get_content_charset())
    print("Content-Transfer-Encoding:", text_part.get("Content-Transfer-Encoding"))

    # Keep the stored payload unchanged, content-transfer decoding is performed in Step 3.
    payload_stored = text_part.get_payload(decode=False)

    print_section("BODY PAYLOAD (as stored, CTE not decoded)")
    print(payload_stored)

    print_section("BODY PAYLOAD repr() (as stored)")
    print(repr(payload_stored))

    return msg, text_part
