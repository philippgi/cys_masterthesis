from __future__ import annotations

import re
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

from config import BASE_DIR, SOCKET_TIMEOUT, SPAMD_HOST, SPAMD_PORT
from src.main_evaluation.spamassassin_evaluation.runner import (
    SpamdClient,
    derive_salt_location,
    parse_x_spam_status,
    read_email_bytes,
)

OUTPUT_ROOT = BASE_DIR / "data/output/pilot/sa/bayes"
DISCOVERY_DIR = OUTPUT_ROOT / "discovery"
TEST_UNSALTED_DIR = OUTPUT_ROOT / "test_unsalted"
TEST_SALTED_DIR = OUTPUT_ROOT / "test_salted"
RESULTS_DIR = OUTPUT_ROOT / "results"

SPAMMY_HEADER = "X-Spam-Spammy"
HAMMY_HEADER = "X-Spam-Hammy"
TOKEN_SPLIT_RE = re.compile(r"\s*,\s*")


def parse_token_header(value: str) -> list[str]:
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
    message_bytes = read_email_bytes(email_path)
    protocol_line, spamd_headers, returned_message = client.scan_email(message_bytes)

    parsed_msg = BytesParser(policy=policy.default).parsebytes(returned_message)
    x_spam_status = str(parsed_msg.get("X-Spam-Status", "")).replace("\n", " ").strip()
    spam_flag, score, threshold, rule_names = parse_x_spam_status(x_spam_status)

    salting_meta = salting_meta or {}
    n_insert_subject = salting_meta.get("n_insert_subject", "")
    n_insert_body = salting_meta.get("n_insert_body", "")

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


def wait_until_spamd_ready(probe_path: Path, timeout_seconds: int = 90, poll_interval: float = 2.0) -> None:
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
    return [
        rule.strip()
        for rule in str(row.get("rules", "")).split("|")
        if rule.strip() and "=" not in rule
    ]


def extract_bayes_rules(rules: list[str]) -> list[str]:
    return [rule for rule in rules if rule.startswith("BAYES_")]
