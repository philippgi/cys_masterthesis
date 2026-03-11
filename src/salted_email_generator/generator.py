#!/usr/bin/env python3
"""
Core logic for generating salted .eml files.
This module creates salted variants of selected spam emails by inserting
invisible Unicode characters into trigger words.

Salting strategy:
- Subject: modify the first trigger occurrence
- Body: modify the first three trigger occurrences
- Position: insert the Unicode codepoint after the second character

The module preserves the original email structure as far as practical,
while replacing only:
- the Subject header
- text/plain
"""

import csv
import json
import re

from copy import deepcopy
from pathlib import Path
from email import policy
from email import encoders
from email.parser import BytesParser
from email.generator import BytesGenerator

from src.trigger_vocabulary.email_extract import safe_charset

TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


def read_candidate_rows(csv_path: Path) -> list[dict]:
    """
    Reads the salted candidate CSV produced by the trigger_coverage step.
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_trigger_words(json_path: Path) -> set[str]:
    """
    Loads trigger tokens from a trigger vocabulary json file.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {entry["token"] for entry in data["triggers"]}


def parse_email(email_path: Path):
    """
    Parses an RFC 5322 email file into an EmailMessage object.

    If the file begins with an mbox-style 'From ' line, it is removed before
    parsing because it is not part of the RFC 5322 header block.
    """
    raw = email_path.read_bytes()
    mbox_from_line = None

    if raw.startswith(b"From "):
        first_nl = raw.find(b"\n")
        if first_nl != -1:
            mbox_from_line = raw[: first_nl + 1]
            raw = raw[first_nl + 1:]

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    return msg, mbox_from_line


def get_decoded_text_plain(part) -> str:
    """
    Returns the decoded text/plain payload.
    """
    try:
        return part.get_content()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        charset = safe_charset(part.get_content_charset())
        return payload.decode(charset, errors="replace")

def replace_text_plain_payload_preserve_format(part, new_text: str) -> None:
    """
    Replaces the payload of an explicit text/plain part while preserving the
    original charset and Content-Transfer-Encoding as far as possible.
    """
    charset = safe_charset(part.get_content_charset())
    original_cte = (part.get("Content-Transfer-Encoding") or "").lower().strip()

    try:
        new_bytes = new_text.encode(charset)
    except Exception:
        charset = "utf-8"
        new_bytes = new_text.encode(charset)

    # remove old payload + old CTE header
    part.set_payload(new_bytes)
    if part["Content-Transfer-Encoding"]:
        del part["Content-Transfer-Encoding"]

    # preserve/update charset on existing Content-Type header
    if part.get("Content-Type") is not None:
        part.set_param("charset", charset, header="Content-Type")

    # re-apply original transfer encoding as far as possible
    if original_cte == "base64":
        encoders.encode_base64(part)
    elif original_cte == "quoted-printable":
        encoders.encode_quopri(part)
    elif original_cte == "7bit":
        # only valid for pure ASCII
        try:
            new_bytes.decode("ascii")
            part["Content-Transfer-Encoding"] = "7bit"
        except UnicodeDecodeError:
            part["Content-Transfer-Encoding"] = "8bit"
    elif original_cte in {"8bit", "binary"}:
        part["Content-Transfer-Encoding"] = original_cte
    else:
        # fallback if header was missing/unknown
        try:
            new_bytes.decode("ascii")
            part["Content-Transfer-Encoding"] = "7bit"
        except UnicodeDecodeError:
            part["Content-Transfer-Encoding"] = "8bit"


def salt_token(token: str, codepoint: str, insert_after_index: int) -> str:
    """
    Inserts the given Unicode codepoint into a token after the configured
    character index.
    """
    return token[:insert_after_index] + codepoint + token[insert_after_index:]


def find_trigger_matches(text: str, trigger_words: set[str]) -> list:
    """
    Finds trigger-word matches in a decoded text string.
    Matching is case-insensitive against the trigger vocabulary.
    """
    matches = []

    for match in TOKEN_RE.finditer(text):
        token = match.group(0)
        if token.lower() in trigger_words:
            matches.append(match)

    return matches


def apply_salting_to_text(
    text: str,
    trigger_words: set[str],
    codepoint: str,
    max_insertions: int,
    insert_after_index: int,
) -> tuple[str, list[dict], int]:
    """
    Applies salting to the first matching trigger occurrences in a text field.
    """
    matches = find_trigger_matches(text, trigger_words)
    selected_matches = matches[:max_insertions]

    if not selected_matches:
        return text, [], 0

    salted_text = text
    targets = []

    # Replace from right to left so offsets remain stable.
    for match in reversed(selected_matches):
        original_token = match.group(0)
        salted_version = salt_token(
            original_token,
            codepoint,
            insert_after_index,
        )

        start = match.start()
        end = match.end()

        salted_text = salted_text[:start] + salted_version + salted_text[end:]

        targets.append(
            {
                "original_token": original_token,
                "salted_token": salted_version,
                "start": start,
                "end": end,
            }
        )

    targets.reverse()
    return salted_text, targets, len(targets)


def iter_text_plain_parts(msg):
    """
    Yields all non-attachment text/plain parts of a message,
    but only if text/plain is explicitly declared in the Content-Type header.
    This avoids implicitly treating malformed or type-less messages as plain text
    and prevents unintended MIME rewriting during salting.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get("Content-Type") is None:
                continue
            if part.get_content_type() != "text/plain":
                continue
            yield part
    else:
        if msg.get("Content-Type") is not None and msg.get_content_type() == "text/plain":
            yield msg


def replace_subject(msg, new_subject: str) -> None:
    """
    Replaces the Subject header of the message.
    """
    if "Subject" in msg:
        msg.replace_header("Subject", new_subject)
    else:
        msg["Subject"] = new_subject


def apply_salting_to_message(
    original_msg,
    trigger_words: set[str],
    codepoint: str,
    subject_max_insertions: int,
    body_max_insertions: int,
    insert_after_index: int,
):
    """
    Applies subject/body salting to a parsed email message and returns a
    modified copy together with logging information.
    """
    msg = deepcopy(original_msg)

    # Subject salting
    original_subject = str(msg.get("Subject", "") or "")
    salted_subject, subject_targets, n_insert_subject = apply_salting_to_text(
        text=original_subject,
        trigger_words=trigger_words,
        codepoint=codepoint,
        max_insertions=subject_max_insertions,
        insert_after_index=insert_after_index,
    )
    replace_subject(msg, salted_subject)

    # Body salting across text/plain parts, globally capped at body_max_insertions
    remaining_body_insertions = body_max_insertions
    body_targets = []
    n_insert_body = 0
    body_part_found = False

    for part in iter_text_plain_parts(msg):
        body_part_found = True

        if remaining_body_insertions <= 0:
            break

        original_text = get_decoded_text_plain(part)

        salted_text, part_targets, part_insertions = apply_salting_to_text(
            text=original_text,
            trigger_words=trigger_words,
            codepoint=codepoint,
            max_insertions=remaining_body_insertions,
            insert_after_index=insert_after_index,
        )

        if part_insertions > 0:
            replace_text_plain_payload_preserve_format(part, salted_text)
            body_targets.extend(part_targets)
            n_insert_body += part_insertions
            remaining_body_insertions -= part_insertions

    return msg, subject_targets, body_targets, n_insert_subject, n_insert_body, body_part_found


def build_variant_filename(
    original_filename: str,
    vocab_type: str,
    codepoint_name: str,
) -> str:
    """
    Builds the salted output filename based on the original email filename.
    """
    source_path = Path(original_filename)
    stem = source_path.stem
    suffix = source_path.suffix or ".eml"

    return f"{stem}__salted__{vocab_type}__cp{codepoint_name}{suffix}"


def write_email(msg, output_path: Path, mbox_from_line: bytes | None = None) -> None:
    """
    Serializes an EmailMessage object to an .eml file.
    """
    with open(output_path, "wb") as f:
        if mbox_from_line is not None:
            f.write(mbox_from_line)
        generator = BytesGenerator(f, policy=policy.default)
        generator.flatten(msg)


def write_salting_log(rows: list[dict], technical_csv: Path, readable_csv: Path) -> None:
    """
    Writes both the technical salting log and a report.

    technical_csv:
        Full log including json target structures.

    readable_csv:
        Simplified log showing which tokens were modified.
    """

    if not rows:
        return

    tech_rows = []
    readable_rows = []

    for row in rows:

        # technical log (original format)
        tech_rows.append(
            {
                "message_id": row["message_id"],
                "variant_filename": row["variant_filename"],
                "vocab_type": row["vocab_type"],
                "codepoint": row["codepoint"],
                "n_insert_subject": row["n_insert_subject"],
                "n_insert_body": row["n_insert_body"],
                "body_part_found": row["body_part_found"],
                "subject_targets": json.dumps(row["subject_targets"], ensure_ascii=False),
                "body_targets": json.dumps(row["body_targets"], ensure_ascii=False),
            }
        )

        # readable log
        subject_original = [t["original_token"] for t in row["subject_targets"]]
        subject_salted = [t["salted_token"] for t in row["subject_targets"]]

        body_original = [t["original_token"] for t in row["body_targets"]]
        body_salted = [t["salted_token"] for t in row["body_targets"]]

        readable_rows.append(
            {
                "message_id": row["message_id"],
                "variant_filename": row["variant_filename"],
                "vocab_type": row["vocab_type"],
                "codepoint": row["codepoint"],
                "subject_original_tokens": ", ".join(subject_original),
                "subject_salted_tokens": ", ".join(subject_salted),
                "body_original_tokens": ", ".join(body_original),
                "body_salted_tokens": ", ".join(body_salted),
            }
        )

    # write technical CSV
    with open(technical_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=tech_rows[0].keys())
        writer.writeheader()
        writer.writerows(tech_rows)

    # write readable CSV
    with open(readable_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=readable_rows[0].keys())
        writer.writeheader()
        writer.writerows(readable_rows)