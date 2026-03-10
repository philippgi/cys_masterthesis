#!/usr/bin/env python3
"""
This module extracts the Subject header and the textual message body
(text/plain) from emails.
"""
from pathlib import Path
from email import policy
from email.parser import BytesParser
import codecs


def extract_subject_and_text_plain(path: Path) -> tuple[str, str]:
    """
    Extracts the Subject header and concatenated text/plain body from an email file.

    This function represents a practical approximation of the receiver-side preprocessing pipeline,
    described in the thesis:
    - Raw bytes are parsed into a MIME message
    - Transfer encodings and character sets are decoded
    - Only semantically relevant text/plain parts are retained

    Args: path (Path): Path to the template files.
    Returns:
        tuple[str, str]:
            - subject (str): Decoded Subject header
            - body_plain (str): Normalized plain-text body
    """
    raw = path.read_bytes()

    # The leading "From " line in the email templates is not an RFC 822 header and must be removed
    if raw.startswith(b"From "):
        first_nl = raw.find(b"\n")
        if first_nl != -1:
            raw = raw[first_nl + 1 :]

    # Parse, extract Subject header and get text/plain payload
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    subject = str(msg.get("Subject", "") or "").strip()
    text_parts: list[str] = []

    def is_attachment(part) -> bool:
        """
        Determines whether a MIME part is an attachment.
        """
        return part.get_content_disposition() == "attachment"

    # Only consider plain-text parts and ignore file attachments
    # Fallback for malformed messages: decode bytes manually -> use validated charset or UTF-8
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/plain":
                continue
            if is_attachment(part):
                continue
            try:
                text_parts.append(part.get_content())
            except Exception:
                payload = part.get_payload(decode=True) or b""
                charset = safe_charset(part.get_content_charset())
                text_parts.append(payload.decode(charset, errors="replace"))
    else:
        # Non-multipart message with a single payload
        if msg.get_content_type() == "text/plain":
            try:
                text_parts.append(msg.get_content())
            except Exception:
                payload = msg.get_payload(decode=True) or b""
                charset = safe_charset(msg.get_content_charset())
                text_parts.append(payload.decode(charset, errors="replace"))

    # Normalize and concatenate all extracted text parts
    body_plain = "\n".join(t.strip() for t in text_parts if t and t.strip()).strip()
    return subject, body_plain


def safe_charset(name: str | None) -> str:
    """
    Normalizes and validates a charset name.
    This helper ensures that decoding always succeeds by falling back to UTF-8 when necessary.

    Args: Charset name as declared in the MIME part of the file.
    Returns: A valid Python codec name of the used charset.
    """

    # Missing charset -> assume UTF-8
    if not name:
        return "utf-8"

    # Normalize seen formatting issues
    name = name.strip().strip('"').strip("'").lower()

    # Some templates uses placeholders instead of real charset names
    if name in {"default_charset", "default-charset", "unknown", "undefined"}:
        return "utf-8"

    # Verify that Python actually knows this codec
    try:
        codecs.lookup(name)
        return name
    except LookupError:
        return "utf-8"
