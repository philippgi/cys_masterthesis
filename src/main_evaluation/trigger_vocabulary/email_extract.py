#!/usr/bin/env python3
"""
Extracts the decoded Subject and non-attachment text/plain content from emails.

The helper performs MIME parsing, content decoding, charset handling, and
plain-text selection for downstream vocabulary and coverage analysis.
"""

from pathlib import Path
from email import policy
from email.parser import BytesParser
import codecs


def extract_subject_and_text_plain(path: Path) -> tuple[str, str]:
    """
    Extract the decoded Subject and concatenated text/plain body from an email.

    Args:
        path (Path): Path to the serialized email message.

    Returns:
        tuple[str, str]: Decoded Subject and concatenated plain-text body.
    """

    raw = path.read_bytes()

    # Remove an mbox-style From line because it is not part of the RFC 5322 message headers.
    if raw.startswith(b"From "):
        first_nl = raw.find(b"\n")
        if first_nl != -1:
            raw = raw[first_nl + 1 :]

    # Parse the message and extract the decoded Subject and eligible plain-text parts.
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    subject = str(msg.get("Subject", "") or "").strip()
    text_parts: list[str] = []

    def is_attachment(part) -> bool:
        return part.get_content_disposition() == "attachment"

    # Include only non-attachment text/plain parts and fall back to manual decoding if needed.
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/plain":
                continue
            if is_attachment(part):
                continue
            try:
                text_parts.append(part.get_content())
            # Fall back to explicit payload and charset decoding if get_content() fails.
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

    # Concatenate the extracted plain-text parts into one normalized body string.
    body_plain = "\n".join(t.strip() for t in text_parts if t and t.strip()).strip()
    return subject, body_plain


def safe_charset(name: str | None) -> str:
    """
    Normalize and validate a MIME charset name.

    Args:
        name (str | None): Charset declared by the MIME part.

    Returns:
        str: Valid Python codec name, falling back to UTF-8 when necessary.
    """

    # Use UTF-8 when no charset is declared.
    if not name:
        return "utf-8"

    # Normalize common formatting variations in charset declarations.
    name = name.strip().strip('"').strip("'").lower()

    # Replace known placeholder charset values with UTF-8.
    if name in {"default_charset", "default-charset", "unknown", "undefined"}:
        return "utf-8"

    # Verify that the declared charset is supported by Python.
    try:
        codecs.lookup(name)
        return name
    except LookupError:
        return "utf-8"
