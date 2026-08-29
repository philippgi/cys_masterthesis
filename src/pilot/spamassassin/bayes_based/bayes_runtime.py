"""
Provides shared runtime helpers for the SpamAssassin Bayes pilot.

The module centralizes output paths, SpamAssassin scan handling, Bayes token
parsing, readiness checks, and rule extraction used across the pilot workflow.
"""

from __future__ import annotations

import re
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

from config import (
    PILOT_SA_BAYES_OUTPUT_DIR,
    PILOT_SA_BAYES_READY_POLL_INTERVAL,
    PILOT_SA_BAYES_READY_TIMEOUT_SECONDS,
    SOCKET_TIMEOUT,
    SPAMD_HOST,
    SPAMD_PORT,
)
from src.main_evaluation.spamassassin_evaluation.runner import (
    SpamdClient,
    derive_salt_location,
    parse_x_spam_status,
    read_email_bytes,
)

OUTPUT_ROOT = PILOT_SA_BAYES_OUTPUT_DIR
DISCOVERY_DIR = OUTPUT_ROOT / "discovery"
TEST_UNSALTED_DIR = OUTPUT_ROOT / "eval/test_unsalted"
TEST_SALTED_DIR = OUTPUT_ROOT / "eval/test_salted"
RESULTS_DIR = OUTPUT_ROOT / "eval"

SPAMMY_HEADER = "X-Spam-Spammy"
HAMMY_HEADER = "X-Spam-Hammy"
TOKEN_SPLIT_RE = re.compile(r"\s*,\s*")


def parse_token_header(value: str) -> list[str]:
    """
    Parse a comma-separated SpamAssassin token header.

    Args:
        value (str): Raw token header value.

    Returns:
        list[str]: Parsed non-empty token values.
    """

    raw = str(value or "").strip()
    if not raw:
        return []

    tokens: list[str] = []
    for item in TOKEN_SPLIT_RE.split(raw):
        token = item.strip()
        if token:
            tokens.append(token)
    return tokens


def scan_email_with_details(
    client: SpamdClient,
    email_path: Path,
    dataset: str,
    label: str,
    message_id: str,
    variant_filename: str = "",
    salting_meta: dict | None = None,
) -> dict:
    """
    Scan an email and extract normalized and Bayes-specific result data.

    Args:
        client (SpamdClient): Connected SpamAssassin client.
        email_path (Path): Path to the email message.
        dataset (str): Dataset identifier used for result reporting.
        label (str): Message class label.
        message_id (str): Message identifier.
        variant_filename (str): Filename of the evaluated salted variant.
        salting_meta (dict | None): Optional salting metadata.

    Returns:
        dict: Normalized scan result, parsed message, returned message bytes,
        and extracted spammy and hammy Bayes tokens.
    """

    message_bytes = read_email_bytes(email_path)
    protocol_line, spamd_headers, returned_message = client.scan_email(message_bytes)

    # Parse the returned message so Bayes-related headers can be inspected directly.
    parsed_msg = BytesParser(policy=policy.default).parsebytes(returned_message)
    x_spam_status = str(parsed_msg.get("X-Spam-Status", "")).replace("\n", " ").strip()
    spam_flag, score, threshold, rule_names = parse_x_spam_status(x_spam_status)

    salting_meta = salting_meta or {}
    n_insert_subject = salting_meta.get("n_insert_subject", "")
    n_insert_body = salting_meta.get("n_insert_body", "")

    # Return both normalized reporting data and Bayes-specific artifacts.
    return {
        "row": {
            "dataset": dataset,
            "label": label,
            "message_id": message_id,
            "variant_filename": variant_filename,
            "vocab_type": salting_meta.get("vocab_type", ""),
            "codepoint": salting_meta.get("codepoint", ""),
            "salt_location": derive_salt_location(n_insert_subject, n_insert_body),
            "n_insert_subject": n_insert_subject,
            "n_insert_body": n_insert_body,
            "spam_flag": spam_flag,
            "score": score,
            "threshold": threshold,
            "rule_count": len(rule_names),
            "rules": "|".join(rule_names),
            "protocol_line": protocol_line,
            "spamd_headers": " | ".join(spamd_headers).replace("\t", " ").replace("\n", " "),
        },
        "parsed_msg": parsed_msg,
        "returned_message": returned_message,
        "spammy_tokens": parse_token_header(parsed_msg.get(SPAMMY_HEADER, "")),
        "hammy_tokens": parse_token_header(parsed_msg.get(HAMMY_HEADER, "")),
    }


def wait_until_spamd_ready(
    probe_path: Path,
    timeout_seconds: int | None = None,
    poll_interval: float | None = None,
) -> None:
    """
    Wait until SpamAssassin successfully scans a probe message.

    Args:
        probe_path (Path): Message used for readiness checks.
        timeout_seconds (int | None): Maximum waiting period in seconds.
        poll_interval (float | None): Delay between consecutive checks.

    Raises:
        TimeoutError: If SpamAssassin does not become ready within the timeout.
    """

    timeout_seconds = (
        PILOT_SA_BAYES_READY_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    )
    poll_interval = (
        PILOT_SA_BAYES_READY_POLL_INTERVAL if poll_interval is None else poll_interval
    )

    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)
        try:
            scan_email_with_details(
                client=client,
                email_path=probe_path,
                dataset="pilot_probe",
                label="spam",
                message_id="probe",
            )
            return
        except Exception as exc:
            last_error = exc
            time.sleep(poll_interval)
        finally:
            client.close()

    raise TimeoutError(f"SpamAssassin was not ready in time. Last error: {last_error}")


def extract_rules(row: dict) -> list[str]:
    """
    Extract normalized rule names from a result row.

    Args:
        row (dict): Normalized SpamAssassin result row.

    Returns:
        list[str]: Extracted rule names without score fragments.
    """

    return [
        rule.strip()
        for rule in str(row.get("rules", "")).split("|")
        if rule.strip() and "=" not in rule
    ]


def extract_bayes_rules(rules: list[str]) -> list[str]:
    """
    Filter Bayes-related rule symbols from a rule list.

    Args:
        rules (list[str]): SpamAssassin rule names.

    Returns:
        list[str]: Rule names beginning with BAYES_.
    """

    return [rule for rule in rules if rule.startswith("BAYES_")]
