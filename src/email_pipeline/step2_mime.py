#!/usr/bin/env python3

"""
Step 2 - RFC 5322 + MIME Parsing (Structural Representation)
This step transforms the raw RFC 5322 message source (byte stream) into a
structured message object by parsing headers and MIME structure.

Scope of this step:
- Inspect the top-level headers as parsed by a standard-compliant MIME parser.
- Inspect whether the message is multipart and enumerate MIME parts.
- Select the relevant "text/plain" body part for further processing.

Important note:
- This step focuses on "structural parsing" (representation: bytes -> structured message).
- It does NOT perform content-transfer decoding (quoted-printable/base64) or charset
  decoding to Unicode text. Those transformations are handled explicitly in Steps 3-4.

Implementation note:
- Parsing is performed using Pythons standard library "email" package
  ("email.parser.BytesParser" with "policy=compat32").
"""

from email import policy
from email.parser import BytesParser


def step2_parse_mime(raw_bytes):
    """
    Parse raw RFC 5322 bytes into a structured MIME message and select the "text/plain" body part.
    Args:
        raw_bytes (bytes): Raw RFC 5322 message source as received from Step 1.
    Returns:
        tuple:
            msg: Parsed EmailMessage (structured headers + MIME tree).
            text_part: Selected MIME part (EmailMessage) of type "text/plain", or None if no such part exists.
    """

    # Parse raw bytes into a structured EmailMessage (RFC 5322 + MIME structure)
    msg = BytesParser(policy=policy.compat32).parsebytes(raw_bytes)

    # Top-level headers as interpreted by the parser
    print("---- HEADERS (top-level) ----")
    for key, value in msg.items():
        print(f"{key}: {value}")

    # MIME structure: single-part vs multipart, and part enumeration
    print("\n---- MIME STRUCTURE ----")
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

    # Select the relevant "text/plain" body part (used for subsequent steps).
    # For single-part messages, the message itself is the relevant part.
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
    print("\n---- SELECTED PART ----")
    print("Content-Type:", text_part.get_content_type())
    print("Charset:", text_part.get_content_charset())
    print("Content-Transfer-Encoding:", text_part.get("Content-Transfer-Encoding"))

    # Payload as stored in the MIME part
    # Using decode=False, because decoding is performed in Step 3
    payload_stored = text_part.get_payload(decode=False)

    print("\n---- BODY PAYLOAD (as stored, CTE not decoded) ----")
    print(payload_stored)

    print("\n---- BODY PAYLOAD repr() (as stored) ----")
    print(repr(payload_stored))

    return msg, text_part
