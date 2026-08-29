"""
Builds paired unsalted and salted messages for the SpamAssassin rule-based pilot.

Configured target tokens in the Subject and body are modified with the selected
zero-width Unicode character. Both variants are serialized as RFC 5322 messages
for subsequent evaluation.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from config import PILOT_SA_RULE_INSERT_AFTER_INDEX


def _salt_token(
    token: str,
    codepoint: str,
    insert_after_index: int = PILOT_SA_RULE_INSERT_AFTER_INDEX,
) -> str:
    """
    Insert a zero-width code point at a configured position within a token.

    Args:
        token (str): Token to modify.
        codepoint (str): Unicode character to insert.
        insert_after_index (int): Position after which the character is inserted.

    Returns:
        str: Salted token.
    """

    if not token:
        return token

    idx = max(1, min(insert_after_index, len(token)))
    return token[:idx] + codepoint + token[idx:]


def _apply_salting(
    text: str,
    targets: tuple[str, ...],
    codepoint: str,
    insert_after_index: int = PILOT_SA_RULE_INSERT_AFTER_INDEX,
) -> tuple[str, int]:
    """
    Salt the first occurrence of each configured target token.

    Args:
        text (str): Subject or body text to modify.
        targets (tuple[str, ...]): Tokens targeted for salting.
        codepoint (str): Unicode character to insert.
        insert_after_index (int): Position within each token used for insertion.

    Returns:
        tuple[str, int]: Salted text and number of modified token occurrences.
    """

    salted = text
    insertions = 0

    for token in targets:
        if token in salted:
            replacement = _salt_token(
                token,
                codepoint,
                insert_after_index=insert_after_index,
            )
            # Modify only the first matching occurrence of each target token.
            salted = salted.replace(token, replacement, 1)
            insertions += 1

    return salted, insertions


def _build_message(subject: str, body: str, from_addr: str, to_addr: str) -> bytes:
    """
    Build and serialize a plain-text pilot email.

    Args:
        subject (str): Message subject.
        body (str): Plain-text message body.
        from_addr (str): Sender address.
        to_addr (str): Recipient address.

    Returns:
        bytes: Serialized RFC 5322 message.
    """

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="pilot.example.test")
    msg.set_content(body)
    return msg.as_bytes()


def create_paired_bytes(
    subject: str,
    body: str,
    target_tokens_subject: tuple[str, ...],
    target_tokens_body: tuple[str, ...],
    codepoint: str,
    from_addr: str,
    to_addr: str,
    insert_after_index: int = PILOT_SA_RULE_INSERT_AFTER_INDEX,
) -> tuple[bytes, bytes, dict]:
    """
    Create paired unsalted and salted versions of a pilot email.

    Args:
        subject (str): Original message subject.
        body (str): Original plain-text message body.
        target_tokens_subject (tuple[str, ...]): Subject tokens targeted for salting.
        target_tokens_body (tuple[str, ...]): Body tokens targeted for salting.
        codepoint (str): Unicode character to insert.
        from_addr (str): Sender address.
        to_addr (str): Recipient address.
        insert_after_index (int): Position within target tokens used for insertion.

    Returns:
        tuple[bytes, bytes, dict]: Unsalted message, salted message, and insertion counts.
    """

    salted_subject, n_insert_subject = _apply_salting(
        text=subject,
        targets=target_tokens_subject,
        codepoint=codepoint,
        insert_after_index=insert_after_index,
    )
    salted_body, n_insert_body = _apply_salting(
        text=body,
        targets=target_tokens_body,
        codepoint=codepoint,
        insert_after_index=insert_after_index,
    )

    unsalted_bytes = _build_message(subject, body, from_addr, to_addr)
    salted_bytes = _build_message(salted_subject, salted_body, from_addr, to_addr)

    counts = {
        "n_insert_subject": n_insert_subject,
        "n_insert_body": n_insert_body,
    }

    return unsalted_bytes, salted_bytes, counts


def write_message(path: Path, content: bytes) -> None:
    """
    Write a serialized email message to disk.

    Args:
        path (Path): Destination file path.
        content (bytes): Serialized message content.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
