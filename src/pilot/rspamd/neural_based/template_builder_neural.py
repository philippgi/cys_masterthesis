"""
Builds paired unsalted and salted email messages for the Rspamd neural pilot.

Target tokens in the Subject and body are modified according to the configured
salting mode and insertion limits. Both variants are serialized as UTF-8
RFC 5322 messages for subsequent evaluation.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from config import (
    PILOT_RS_NEURAL_SALT_MODE,
    PILOT_RS_NEURAL_INSERT_AFTER_INDEX,
    PILOT_RS_NEURAL_SUBJECT_MAX_INSERTIONS,
    PILOT_RS_NEURAL_BODY_MAX_INSERTIONS,
)


def _salt_token(token: str, codepoint: str, insert_after_index: int) -> str:
    if not token:
        return token

    idx = max(1, min(insert_after_index, len(token)))
    return token[:idx] + codepoint + token[idx:]


def _salt_token_fragment(token: str, codepoint: str) -> str:
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
    salted = text
    insertions = 0

    for token in targets:
        if insertions >= max_insertions:
            break

        if token in salted:
            if PILOT_RS_NEURAL_SALT_MODE == "single":
                replacement = _salt_token(
                    token,
                    codepoint,
                    PILOT_RS_NEURAL_INSERT_AFTER_INDEX,
                )
            else:
                replacement = _salt_token_fragment(token, codepoint)

            salted = salted.replace(token, replacement, 1)
            insertions += 1

    return salted, insertions


def _build_message(
    subject: str,
    body: str,
    from_addr: str,
    to_addr: str,
) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="rspamd.pilot.test")

    msg.set_content(
        body,
        subtype="plain",
        charset="utf-8",
        cte="8bit",
    )

    return msg.as_bytes()


def create_paired_bytes(
    subject: str,
    body: str,
    target_tokens_subject: tuple[str, ...],
    target_tokens_body: tuple[str, ...],
    codepoint: str,
    from_addr: str,
    to_addr: str,
) -> tuple[bytes, bytes, dict]:
    salted_subject, n_insert_subject = _apply_salting(
        text=subject,
        targets=target_tokens_subject,
        codepoint=codepoint,
        max_insertions=PILOT_RS_NEURAL_SUBJECT_MAX_INSERTIONS,
    )

    salted_body, n_insert_body = _apply_salting(
        text=body,
        targets=target_tokens_body,
        codepoint=codepoint,
        max_insertions=PILOT_RS_NEURAL_BODY_MAX_INSERTIONS,
    )

    unsalted_bytes = _build_message(subject, body, from_addr, to_addr)
    salted_bytes = _build_message(salted_subject, salted_body, from_addr, to_addr)

    counts = {
        "n_insert_subject": n_insert_subject,
        "n_insert_body": n_insert_body,
    }

    return unsalted_bytes, salted_bytes, counts


def write_message(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)