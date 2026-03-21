from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


def _salt_token(token: str, codepoint: str, insert_after_index: int = 1) -> str:
    if not token:
        return token

    idx = max(1, min(insert_after_index, len(token)))
    return token[:idx] + codepoint + token[idx:]


def _apply_salting(
    text: str,
    targets: tuple[str, ...],
    codepoint: str,
    insert_after_index: int = 1,
) -> tuple[str, int]:
    salted = text
    insertions = 0

    for token in targets:
        if token in salted:
            replacement = _salt_token(token, codepoint, insert_after_index=insert_after_index)
            salted = salted.replace(token, replacement, 1)
            insertions += 1

    return salted, insertions


def _build_message(subject: str, body: str, from_addr: str, to_addr: str) -> bytes:
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
) -> tuple[bytes, bytes, dict]:
    salted_subject, n_insert_subject = _apply_salting(
        text=subject,
        targets=target_tokens_subject,
        codepoint=codepoint,
    )
    salted_body, n_insert_body = _apply_salting(
        text=body,
        targets=target_tokens_body,
        codepoint=codepoint,
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