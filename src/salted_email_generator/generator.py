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
- text/plain MIME parts
"""

import csv
import json
import re
from copy import deepcopy
from pathlib import Path
from email import policy
from email.parser import BytesParser
from email.generator import BytesGenerator
from io import BytesIO

from src.trigger_vocabulary.email_extract import safe_charset


TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


def read_candidate_rows(csv_path: Path) -> list[dict]:
    """
    Reads the salted candidate CSV produced by the candidate selection step.
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_trigger_words(json_path: Path) -> set[str]:
    """
    Loads trigger tokens from a trigger vocabulary JSON file.
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

    if raw.startswith(b"From "):
        first_nl = raw.find(b"\n")
        if first_nl != -1:
            raw = raw[first_nl + 1:]

    return BytesParser(policy=policy.default).parsebytes(raw)


def get_decoded_text_plain(part) -> str:
    """
    Returns the decoded text/plain payload of a MIME part.
    """
    try:
        return part.get_content()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        charset = safe_charset(part.get_content_charset())
        return payload.decode(charset, errors="replace")


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
    Yields all non-attachment text/plain parts of a message.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() != "text/plain":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            yield part
    else:
        if msg.get_content_type() == "text/plain":
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

    for part in iter_text_plain_parts(msg):
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
            part.set_content(salted_text, subtype="plain", charset="utf-8")
            body_targets.extend(part_targets)
            n_insert_body += part_insertions
            remaining_body_insertions -= part_insertions

    return msg, subject_targets, body_targets, n_insert_subject, n_insert_body


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


def write_email(msg, output_path: Path) -> None:
    """
    Serializes an EmailMessage object to an .eml file.
    """
    with open(output_path, "wb") as f:
        generator = BytesGenerator(f, policy=policy.default)
        generator.flatten(msg)


def write_salting_log(rows: list[dict], technical_csv: Path, readable_csv: Path) -> None:
    """
    Writes both the technical salting log and a human readable report.

    technical_csv:
        Full log including JSON target structures (used later for analysis)

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