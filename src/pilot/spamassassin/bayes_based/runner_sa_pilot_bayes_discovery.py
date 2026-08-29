"""
Discovers Bayes-relevant tokens for the SpamAssassin pilot message.

The prepared unsalted message is scanned with the Bayes pilot configuration.
Spammy tokens reported by SpamAssassin are matched against the original Subject
and plain-text body and exported as candidates for the salting evaluation.
"""

from __future__ import annotations

import csv
import json
from email import policy
from email.parser import BytesParser

from config import PILOT_SA_BAYES_CONFIG_NAME, SOCKET_TIMEOUT, SPAMD_HOST, SPAMD_PORT
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.spamassassin_evaluation.runner import SpamdClient
from src.pilot.spamassassin.bayes_based.bayes_cases import SAB001
from src.pilot.spamassassin.bayes_based.bayes_runtime import (
    DISCOVERY_DIR,
    TEST_UNSALTED_DIR,
    scan_email_with_details,
    wait_until_spamd_ready,
)
from src.utils.console import print_end, print_kv, print_section, print_step


def _write_csv(path, rows: list[dict]) -> None:
    """
    Write token discovery rows to a semicolon-delimited CSV file.

    Args:
        path: Destination CSV path.
        rows (list[dict]): Token discovery records.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path, data: dict) -> None:
    """
    Write discovery metadata to a JSON file.

    Args:
        path: Destination JSON path.
        data (dict): Discovery metadata to export.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _select_tokens_present_in_text(text: str, tokens: list[str]) -> list[str]:
    """
    Select discovered tokens that occur in the provided text.

    Args:
        text (str): Subject or body text to inspect.
        tokens (list[str]): Candidate tokens reported by SpamAssassin.

    Returns:
        list[str]: Tokens present in the text.
    """

    text_lc = (text or "").lower()
    return [token for token in tokens if token and token.lower() in text_lc]


def run_sa_pilot_bayes_discovery() -> None:
    """
    Run Bayes token discovery for the prepared unsalted pilot message.

    The discovered token candidates and scan metadata are exported as CSV,
    JSON, and the returned SpamAssassin message.
    """

    print_step("SA Pilot - Bayes Discovery")

    test_unsalted = TEST_UNSALTED_DIR / f"{SAB001.case_id}_unsalted.eml"
    if not test_unsalted.exists():
        raise FileNotFoundError(
            f"Missing unsalted Bayes pilot mail: {test_unsalted}\n"
            "Run run_sa_pilot_bayes_prepare() first."
        )

    activate_spamassassin_config(PILOT_SA_BAYES_CONFIG_NAME)
    restart_spamassassin()
    wait_until_spamd_ready(test_unsalted)

    client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)
    try:
        scan = scan_email_with_details(
            client=client,
            email_path=test_unsalted,
            dataset="pilot",
            label="spam",
            message_id=SAB001.case_id,
            variant_filename=test_unsalted.name,
        )
    finally:
        client.close()

    # Re-parse the original message to locate discovered tokens in Subject and body.
    raw_msg = test_unsalted.read_bytes()
    parsed_original = BytesParser(policy=policy.default).parsebytes(raw_msg)
    subject_text = str(parsed_original.get("Subject", ""))
    body_part = parsed_original.get_body(preferencelist=("plain",))
    body_text = str(body_part.get_content()) if body_part else ""

    spammy_tokens = scan["spammy_tokens"]
    subject_tokens = _select_tokens_present_in_text(subject_text, spammy_tokens)
    body_tokens = _select_tokens_present_in_text(body_text, spammy_tokens)
    matched_tokens = sorted(set(subject_tokens) | set(body_tokens), key=str.lower)

    # Preserve SpamAssassin's token order while recording where each token occurs.
    token_rows = [
        {
            "token": token,
            "present_in_subject": token in subject_tokens,
            "present_in_body": token in body_tokens,
        }
        for token in spammy_tokens
    ]

    csv_path = DISCOVERY_DIR / f"{SAB001.case_id}_bayes_tokens.csv"
    json_path = DISCOVERY_DIR / f"{SAB001.case_id}_bayes_tokens_summary.json"
    scanned_path = DISCOVERY_DIR / f"{SAB001.case_id}_scanned_unsalted.eml"

    if token_rows:
        _write_csv(csv_path, token_rows)
    else:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("token;present_in_subject;present_in_body\n", encoding="utf-8")

    summary = {
        "case_id": SAB001.case_id,
        "title": SAB001.title,
        "spam_flag": scan["row"]["spam_flag"],
        "score": scan["row"]["score"],
        "threshold": scan["row"]["threshold"],
        "spammy_tokens": spammy_tokens,
        "matched_tokens": matched_tokens,
        "matched_tokens_subject": subject_tokens,
        "matched_tokens_body": body_tokens,
        "n_spammy_tokens": len(spammy_tokens),
        "n_matched_tokens": len(matched_tokens),
        "scanned_message": str(scanned_path),
    }

    _write_json(json_path, summary)
    scanned_path.write_bytes(scan["returned_message"])

    print_section("Discovery")
    print_kv("score", scan["row"]["score"])
    print_kv("spammy_tokens", spammy_tokens)
    print_kv("matched_tokens_subject", subject_tokens)
    print_kv("matched_tokens_body", body_tokens)
    print_end("SA Pilot - Bayes Discovery")
