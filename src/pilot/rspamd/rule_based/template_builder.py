"""
Builds paired unsalted and salted email messages for the Rspamd rule-based pilot.

Target tokens in the Subject and body are modified according to the configured
salting mode and insertion limits. Both message variants are serialized as
UTF-8 RFC 5322 messages for subsequent evaluation.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from config import (
    PILOT_RS_RULE_BODY_MAX_INSERTIONS,
    PILOT_RS_RULE_INSERT_AFTER_INDEX,
    PILOT_RS_RULE_SALT_MODE,
    PILOT_RS_RULE_SUBJECT_MAX_INSERTIONS,
)


# --- Salting helpers ---

def _salt_token(token: str, codepoint: str, insert_after_index: int = 1) -> str:
    """
    Insert one zero-width code point at a configured position within a token.

    Args:
        token (str): Token to modify.
        codepoint (str): Zero-width Unicode character to insert.
        insert_after_index (int): Position after which the code point is inserted.

    Returns:
        str: Salted token.
    """

    if not token:
        return token

    idx = max(1, min(insert_after_index, len(token)))
    return token[:idx] + codepoint + token[idx:]


def _salt_token_fragment(token: str, codepoint: str) -> str:
    """
    Insert a zero-width code point between all characters of a token.

    Args:
        token (str): Token to modify.
        codepoint (str): Zero-width Unicode character to insert.

    Returns:
        str: Fragmented token.
    """

    if not token:
        return token

    result = []
    for i, char in enumerate(token):
        result.append(char)
        if i < len(token) - 1:
            result.append(codepoint)

    return "".join(result)


def _apply_salting(
    text: str,
    targets: tuple[str, ...],
    codepoint: str,
    max_insertions: int,
) -> tuple[str, int]:
    """
    Apply the configured salting mode to matching target tokens.

    Args:
        text (str): Subject or body text to modify.
        targets (tuple[str, ...]): Target tokens considered for salting.
        codepoint (str): Zero-width Unicode character to insert.
        max_insertions (int): Maximum number of target occurrences to modify.

    Returns:
        tuple[str, int]: Salted text and number of modified target occurrences.
    """

    salted = text
    insertions = 0

    for token in targets:
        if insertions >= max_insertions:
            break

        if token in salted:
            if PILOT_RS_RULE_SALT_MODE == "single":
                replacement = _salt_token(
                    token,
                    codepoint,
                    insert_after_index=PILOT_RS_RULE_INSERT_AFTER_INDEX,
                )
            elif PILOT_RS_RULE_SALT_MODE == "fragment":
                replacement = _salt_token_fragment(token, codepoint)
            else:
                replacement = token

            # Modify at most the first matching occurrence of each target token.
            salted = salted.replace(token, replacement, 1)
            insertions += 1

    return salted, insertions


# --- Message builder ---

def _build_message(
    subject: str,
    body: str,
    from_addr: str,
    to_addr: str,
) -> bytes:
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
    msg["Message-ID"] = make_msgid(domain="rspamd.pilot.test")

    # Use UTF-8 with 8bit transfer encoding for the controlled pilot messages.
    msg.set_content(
        body,
        subtype="plain",
        charset="utf-8",
        cte="8bit",
    )

    return msg.as_bytes()


# --- Public API ---

def create_paired_bytes(
    subject: str,
    body: str,
    target_tokens_subject: tuple[str, ...],
    target_tokens_body: tuple[str, ...],
    codepoint: str,
    from_addr: str,
    to_addr: str,
) -> tuple[bytes, bytes, dict]:
    """
    Create paired unsalted and salted versions of a pilot email.

    Args:
        subject (str): Original message subject.
        body (str): Original plain-text message body.
        target_tokens_subject (tuple[str, ...]): Subject tokens targeted for salting.
        target_tokens_body (tuple[str, ...]): Body tokens targeted for salting.
        codepoint (str): Zero-width Unicode character to insert.
        from_addr (str): Sender address.
        to_addr (str): Recipient address.

    Returns:
        tuple[bytes, bytes, dict]: Unsalted message, salted message, and insertion counts.
    """

    salted_subject, n_insert_subject = _apply_salting(
        text=subject,
        targets=target_tokens_subject,
        codepoint=codepoint,
        max_insertions=PILOT_RS_RULE_SUBJECT_MAX_INSERTIONS,
    )

    salted_body, n_insert_body = _apply_salting(
        text=body,
        targets=target_tokens_body,
        codepoint=codepoint,
        max_insertions=PILOT_RS_RULE_BODY_MAX_INSERTIONS,
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
