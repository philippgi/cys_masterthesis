#!/usr/bin/env python3
"""
Generates salted email variants by inserting zero-width Unicode characters
into trigger-word occurrences.

The original message structure is preserved as far as possible. Salting is
restricted to the Subject header and explicitly declared non-attachment
text/plain MIME parts.
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

from src.main_evaluation.trigger_vocabulary.email_extract import safe_charset

TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


def read_candidate_rows(csv_path: Path) -> list[dict]:
    """
    Load candidate messages produced by the trigger-coverage stage.

    Args:
        csv_path (Path): Path to the candidate CSV file.

    Returns:
        list[dict]: Candidate message records.
    """

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_trigger_words(json_path: Path) -> set[str]:
    """
    Load trigger tokens from a generated vocabulary file.

    Args:
        json_path (Path): Path to the vocabulary JSON file.

    Returns:
        set[str]: Trigger tokens contained in the vocabulary.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {entry["token"] for entry in data["triggers"]}


def parse_email(email_path: Path):
    """
    Parse an RFC 5322 email while preserving an optional mbox From line.

    Args:
        email_path (Path): Path to the serialized email message.

    Returns:
        tuple: Parsed message and optional mbox From line.
    """

    raw = email_path.read_bytes()
    mbox_from_line = None

    # Preserve an mbox-style From line separately because it is not part of RFC 5322 headers.
    if raw.startswith(b"From "):
        first_nl = raw.find(b"\n")
        if first_nl != -1:
            mbox_from_line = raw[: first_nl + 1]
            raw = raw[first_nl + 1:]

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    return msg, mbox_from_line


def get_decoded_text_plain(part) -> str:
    """
    Decode the textual content of a text/plain MIME part.

    Args:
        part: MIME part to decode.

    Returns:
        str: Decoded Unicode text.
    """

    try:
        return part.get_content()
    # Fall back to explicit payload and charset decoding if get_content() fails.
    except Exception:
        payload = part.get_payload(decode=True) or b""
        charset = safe_charset(part.get_content_charset())
        return payload.decode(charset, errors="replace")


def replace_text_plain_payload_preserve_format(part, new_text: str) -> None:
    """
    Replace a text/plain payload while preserving its original encoding metadata
    as far as possible.

    Args:
        part: MIME part whose payload is replaced.
        new_text (str): Modified Unicode text.
    """

    charset = safe_charset(part.get_content_charset())
    original_cte = (part.get("Content-Transfer-Encoding") or "").lower().strip()

    try:
        # Prefer the original charset and fall back to UTF-8 if it cannot encode the salted text.
        new_bytes = new_text.encode(charset)
    except Exception:
        charset = "utf-8"
        new_bytes = new_text.encode(charset)

    # Replace the payload and rebuild the Content-Transfer-Encoding header.
    part.set_payload(new_bytes)
    if part["Content-Transfer-Encoding"]:
        del part["Content-Transfer-Encoding"]

    # Preserve/update charset on existing Content-Type header
    if part.get("Content-Type") is not None:
        part.set_param("charset", charset, header="Content-Type")

    # Reapply the original transfer encoding where possible.
    if original_cte == "base64":
        encoders.encode_base64(part)
    elif original_cte == "quoted-printable":
        encoders.encode_quopri(part)
    elif original_cte == "7bit":
        try:
            new_bytes.decode("ascii")
            part["Content-Transfer-Encoding"] = "7bit"
        except UnicodeDecodeError:
            part["Content-Transfer-Encoding"] = "8bit"
    elif original_cte in {"8bit", "binary"}:
        part["Content-Transfer-Encoding"] = original_cte
    else:
        try:
            new_bytes.decode("ascii")
            part["Content-Transfer-Encoding"] = "7bit"
        except UnicodeDecodeError:
            part["Content-Transfer-Encoding"] = "8bit"


def salt_token(
    token: str,
    codepoint: str,
    insert_after_index: int,
    mode: str = "single",
    fragment_max_positions: int | None = None,
) -> str:
    """
    Insert the configured zero-width character into a token.

    Args:
        token (str): Token to modify.
        codepoint (str): Unicode character to insert.
        insert_after_index (int): Position used by single-mode salting.
        mode (str): Salting mode, either "single" or "fragment".
        fragment_max_positions (int | None): Maximum insertion positions in fragment mode.

    Returns:
        str: Salted token.

    Raises:
        ValueError: If an unsupported salting mode is requested.
    """

    if len(token) < 2:
        return token

    if mode == "single":
        # Clamp the insertion position so the code point remains inside the token.
        safe_index = max(1, min(insert_after_index, len(token) - 1))
        return token[:safe_index] + codepoint + token[safe_index:]

    if mode == "fragment":
        chars = list(token)

        # Fragment mode inserts between characters, never before or after the token.
        possible_positions = list(range(1, len(chars)))

        if fragment_max_positions is not None:
            possible_positions = possible_positions[:fragment_max_positions]

        salted_parts = []
        for idx, ch in enumerate(chars, start=1):
            salted_parts.append(ch)
            if idx in possible_positions:
                salted_parts.append(codepoint)

        return "".join(salted_parts)

    raise ValueError(
        f"Invalid salt mode '{mode}'. Expected 'single' or 'fragment'."
    )


def find_trigger_matches(text: str, trigger_words: set[str]) -> list:
    """
    Find case-insensitive trigger-word occurrences in decoded text.

    Args:
        text (str): Text to inspect.
        trigger_words (set[str]): Lowercase trigger vocabulary.

    Returns:
        list: Regex matches corresponding to trigger words.
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
    salt_mode: str = "single",
    fragment_max_positions: int | None = None,
) -> tuple[str, list[dict], int]:
    """
    Salt the first matching trigger-word occurrences in a text field.

    Args:
        text (str): Subject or body text to modify.
        trigger_words (set[str]): Trigger vocabulary.
        codepoint (str): Unicode character to insert.
        max_insertions (int): Maximum number of matching occurrences to modify.
        insert_after_index (int): Position used by single-mode salting.
        salt_mode (str): Salting mode.
        fragment_max_positions (int | None): Maximum fragment-mode insertion positions.

    Returns:
        tuple[str, list[dict], int]: Salted text, modified targets, and insertion count.
    """

    matches = find_trigger_matches(text, trigger_words)
    # Limit salting to the first matching occurrences up to the configured maximum.
    selected_matches = matches[:max_insertions]

    if not selected_matches:
        return text, [], 0

    salted_text = text
    targets = []

    # Replace matches from right to left so earlier character offsets remain valid.
    for match in reversed(selected_matches):
        original_token = match.group(0)
        salted_version = salt_token(
            token=original_token,
            codepoint=codepoint,
            insert_after_index=insert_after_index,
            mode=salt_mode,
            fragment_max_positions=fragment_max_positions,
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
                "salt_mode": salt_mode,
                "fragment_max_positions": fragment_max_positions,
            }
        )

    targets.reverse()
    return salted_text, targets, len(targets)


def iter_text_plain_parts(msg):
    """
    Yield explicitly declared non-attachment text/plain MIME parts.

    Implicit or type-less payloads are excluded to avoid unintended MIME
    rewriting outside the defined salting scope.

    Args:
        msg: Parsed email message.

    Yields:
        Explicit non-attachment text/plain MIME parts.
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
    Replace or add the Subject header.

    Args:
        msg: Parsed email message.
        new_subject (str): Modified Subject value.
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
    salt_mode: str = "single",
    fragment_max_positions: int | None = None,
):
    """
    Apply salting to the Subject and eligible text/plain body parts.

    A deep copy of the original message is modified. Subject and body insertion
    limits are applied independently, while the body limit is shared globally
    across all eligible text/plain MIME parts.

    Args:
        original_msg: Parsed source message.
        trigger_words (set[str]): Trigger vocabulary.
        codepoint (str): Unicode character to insert.
        subject_max_insertions (int): Maximum Subject insertions.
        body_max_insertions (int): Maximum body insertions across all eligible parts.
        insert_after_index (int): Position used by single-mode salting.
        salt_mode (str): Salting mode.
        fragment_max_positions (int | None): Maximum fragment-mode insertion positions.

    Returns:
        tuple: Salted message, Subject targets, body targets, insertion counts,
        and whether an eligible body part was found.
    """

    # Modify a copy so the original parsed message remains unchanged.
    msg = deepcopy(original_msg)

    # Apply the Subject insertion limit independently from the body limit.
    original_subject = str(msg.get("Subject", "") or "")
    salted_subject, subject_targets, n_insert_subject = apply_salting_to_text(
        text=original_subject,
        trigger_words=trigger_words,
        codepoint=codepoint,
        max_insertions=subject_max_insertions,
        insert_after_index=insert_after_index,
        salt_mode=salt_mode,
        fragment_max_positions=fragment_max_positions,
    )
    replace_subject(msg, salted_subject)

    # Share the configured body insertion limit across all eligible text/plain parts.
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
            salt_mode=salt_mode,
            fragment_max_positions=fragment_max_positions,
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
    salt_mode: str = "single",
) -> str:
    """
    Build the deterministic filename of a salted message variant.

    Args:
        original_filename (str): Original message filename.
        vocab_type (str): Trigger vocabulary scope.
        codepoint_name (str): Unicode code-point identifier.
        salt_mode (str): Applied salting mode.

    Returns:
        str: Generated variant filename.
    """

    source_path = Path(original_filename)
    stem = source_path.stem
    suffix = source_path.suffix or ".eml"

    return f"{stem}__salted__{vocab_type}__cp{codepoint_name}__{salt_mode}{suffix}"


def write_email(msg, output_path: Path, mbox_from_line: bytes | None = None) -> None:
    """
    Serialize a modified email message to disk.

    Args:
        msg: Message to serialize.
        output_path (Path): Destination path.
        mbox_from_line (bytes | None): Optional preserved mbox From line.
    """

    with open(output_path, "wb") as f:
        if mbox_from_line is not None:
            f.write(mbox_from_line)
        generator = BytesGenerator(f, policy=policy.default)
        generator.flatten(msg)


def write_salting_log(rows: list[dict], technical_csv: Path, readable_csv: Path) -> None:
    """
    Write technical and human-readable salting logs.

    Args:
        rows (list[dict]): Salting records.
        technical_csv (Path): Destination for complete technical metadata.
        readable_csv (Path): Destination for simplified token-level reporting.
    """

    if not rows:
        return

    tech_rows = []
    readable_rows = []

    for row in rows:
        # Store complete machine-readable salting metadata.
        tech_rows.append(
            {
                "message_id": row["message_id"],
                "variant_filename": row["variant_filename"],
                "vocab_type": row["vocab_type"],
                "codepoint": row["codepoint"],
                "salt_mode": row["salt_mode"],
                "fragment_max_positions": row["fragment_max_positions"],
                "n_insert_subject": row["n_insert_subject"],
                "n_insert_body": row["n_insert_body"],
                "body_part_found": row["body_part_found"],
                "subject_targets": json.dumps(row["subject_targets"], ensure_ascii=False),
                "body_targets": json.dumps(row["body_targets"], ensure_ascii=False),
            }
        )

        # Flatten modified tokens into a human-readable reporting format.
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
                "salt_mode": row["salt_mode"],
                "fragment_max_positions": row["fragment_max_positions"],
                "subject_original_tokens": ", ".join(subject_original),
                "subject_salted_tokens": ", ".join(subject_salted),
                "body_original_tokens": ", ".join(body_original),
                "body_salted_tokens": ", ".join(body_salted),
            }
        )

    with open(technical_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=tech_rows[0].keys())
        writer.writeheader()
        writer.writerows(tech_rows)

    with open(readable_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=readable_rows[0].keys())
        writer.writeheader()
        writer.writerows(readable_rows)