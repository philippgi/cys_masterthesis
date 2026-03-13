#!/usr/bin/env python3
"""
SpamAssassin evaluation runner.

This module evaluates the paired unsalted baseline spam test set
(data/datasets/split/test/spam), the full ham test set
(data/datasets/split/test/ham), and the salted spam variants
(data/output/salted_email_generator/salted_emails) with SpamAssassin.

Important evaluation logic:
- Baseline ham: all ham test emails
- Baseline spam: only original spam emails for which at least one salted
  variant was actually generated
- Salted spam: all generated salted variants

For each scanned email, the module extracts:
    - spam classification
    - score
    - threshold
    - triggered rules

For salted variants, the module also joins metadata from the salting log, such as:
    - vocabulary type
    - used Unicode code point
    - insertion counts in subject and body

Output files:
- spamassassin_results.csv
    Variant-level results (one row per scanned email / salted variant)
- spamassassin_results_paired.csv
    Original-level paired results (one row per original spam email with
    aggregated salted statistics)

All results are written into data/output/spamassassin_evaluation
"""

import csv
import re
import socket
import sys

from collections import defaultdict
from email import policy
from email.parser import BytesParser
from pathlib import Path
from statistics import mean
from tqdm import tqdm
from src.utils.console import print_step, print_section, print_kv, print_end


from config import (
    DATASET_SPLIT,
    OUTPUT_ROOT,
    SALTED_EMAILS_DIR,
    SALTING_LOG_CSV,
    SPAMD_HOST,
    SPAMD_PORT,
    SOCKET_TIMEOUT,
)


# Regular expressions used for parsing SpamAssassin output
SCORE_RE = re.compile(r"score=([-+]?\d+(?:\.\d+)?)")
REQUIRED_RE = re.compile(r"required=([-+]?\d+(?:\.\d+)?)")
TESTS_RE = re.compile(r"tests=([^ ]+)")
CONTENT_LENGTH_RE = re.compile(r"^Content-length:\s*(\d+)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def read_email_bytes(path: Path) -> bytes:
    """
    Reads the raw RFC 5322 email file.
    The full raw message is required because SpamAssassin analyzes both
    headers and body content.
    """
    return path.read_bytes()


def load_salting_log(csv_path: Path) -> dict[str, dict[str, str]]:
    """
    Loads the salting log and indexes it by variant filename.

    Expected key:
        variant_filename
    """
    if not csv_path.exists():
        return {}

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["variant_filename"]: row for row in reader}


def load_salted_source_ids(csv_path: Path) -> set[str]:
    """
    Loads all original message_ids for which at least one salted variant
    was actually generated.
    """
    if not csv_path.exists():
        return set()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["message_id"] for row in reader if row.get("message_id")}


def derive_salt_location(n_insert_subject, n_insert_body) -> str:
    """
    Derives the location label based on insertion.
    Possible locations:
        - none
        - subject
        - body
        - both
    """
    try:
        subject_count = int(n_insert_subject)
    except (TypeError, ValueError):
        subject_count = 0

    try:
        body_count = int(n_insert_body)
    except (TypeError, ValueError):
        body_count = 0

    if subject_count > 0 and body_count > 0:
        return "both"
    if subject_count > 0:
        return "subject"
    if body_count > 0:
        return "body"
    return "none"


def parse_x_spam_status(x_spam_status: str):
    """
    Extracts relevant information from X-Spam-Status.

    Example:
        X-Spam-Status: No, score=1.6 required=5.0 tests=HTML_MESSAGE,BAYES_99

    Extracted:
        - spam_flag
        - score
        - threshold
        - rule_names
    """
    if not x_spam_status:
        return False, None, None, []

    spam_flag = x_spam_status.lower().startswith("yes")

    score_match = SCORE_RE.search(x_spam_status)
    threshold_match = REQUIRED_RE.search(x_spam_status)
    tests_match = TESTS_RE.search(x_spam_status)

    score = float(score_match.group(1)) if score_match else None
    threshold = float(threshold_match.group(1)) if threshold_match else None

    rule_names = []
    if tests_match:
        raw_tests = tests_match.group(1)
        rule_names = [r.strip() for r in raw_tests.split(",") if r.strip()]

    return spam_flag, score, threshold, rule_names


def build_paired_results(rows: list[dict]) -> list[dict]:
    """
    Builds one paired/original-level result row per original spam email.

    Variant-level results already exist in RESULT_CSV:
        one row per scanned email / salted variant

    This function creates original-level paired results:
        one row per original spam email with aggregated salted statistics
    """
    baseline_by_message = {}
    salted_by_message = defaultdict(list)

    for row in rows:
        if row["label"] != "spam":
            continue

        if row["dataset"] == "baseline":
            baseline_by_message[row["message_id"]] = row
        elif row["dataset"] == "salted" and row["message_id"]:
            salted_by_message[row["message_id"]].append(row)

    paired_rows = []

    for message_id, baseline in baseline_by_message.items():
        variants = salted_by_message.get(message_id, [])
        if not variants:
            continue

        variant_scores = [v["score"] for v in variants if v["score"] is not None]
        variant_rule_counts = [v["rule_count"] for v in variants if v["rule_count"] is not None]
        variant_flags = [bool(v["spam_flag"]) for v in variants]

        paired_rows.append(
            {
                "message_id": message_id,
                "baseline_score": baseline["score"],
                "baseline_spam_flag": baseline["spam_flag"],
                "baseline_rule_count": baseline["rule_count"],
                "n_variants": len(variants),
                "salted_score_mean": mean(variant_scores) if variant_scores else None,
                "salted_score_min": min(variant_scores) if variant_scores else None,
                "salted_score_max": max(variant_scores) if variant_scores else None,
                "salted_rule_count_mean": mean(variant_rule_counts) if variant_rule_counts else None,
                "salted_any_spam": any(variant_flags) if variant_flags else False,
                "salted_all_spam": all(variant_flags) if variant_flags else False,
                "salted_any_bypass": any(not f for f in variant_flags) if variant_flags else False,
                "salted_all_bypass": all(not f for f in variant_flags) if variant_flags else False,
            }
        )

    paired_rows.sort(key=lambda row: row["message_id"])
    return paired_rows


# ---------------------------------------------------------------------------
# Spamd client
# ---------------------------------------------------------------------------

class SpamdClient:
    """
    Client for communicating with spamd via a persistent TCP connection.
    The client reconnects automatically if the connection is dropped.
    """

    def __init__(self, host: str, port: int, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.reader = None

    def connect(self) -> None:
        """
        Opens a TCP connection to spamd and prepares a buffered reader.
        """
        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.reader = self.sock.makefile("rb")

    def close(self) -> None:
        """
        Closes the current connection if present.
        """
        try:
            if self.reader is not None:
                self.reader.close()
        except Exception:
            pass

        try:
            if self.sock is not None:
                self.sock.close()
        except Exception:
            pass

        self.reader = None
        self.sock = None

    def ensure_connected(self) -> None:
        """
        Ensures that a connection exists.
        """
        if self.sock is None or self.reader is None:
            self.connect()

    def build_request(self, message_bytes: bytes) -> bytes:
        """
        Builds a SPAMC HEADERS request.

        HEADERS tells spamd to:
            - scan the message
            - return the message with X-Spam-* headers added
        """
        return (
            f"HEADERS SPAMC/1.5\r\n"
            f"Content-length: {len(message_bytes)}\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        ).encode("utf-8") + message_bytes

    def read_response(self):
        """
        Reads one complete spamd response.

        Expected structure:
            SPAMD/1.1 0 EX_OK
            Content-length: ...
            Spam: True/False ; score / threshold
            <empty line>
            <returned message with X-Spam-* headers>
        """
        protocol_line = self.reader.readline()
        if not protocol_line:
            raise ConnectionError("spamd closed the connection before sending a response line.")

        protocol_line = protocol_line.decode("utf-8", errors="replace").rstrip("\r\n")

        spamd_headers = []
        content_length = None

        while True:
            line = self.reader.readline()
            if not line:
                raise ConnectionError("spamd closed the connection while sending response headers.")

            if line == b"\r\n":
                break

            decoded_line = line.decode("utf-8", errors="replace").rstrip("\r\n")
            spamd_headers.append(decoded_line)

            match = CONTENT_LENGTH_RE.match(decoded_line)
            if match:
                content_length = int(match.group(1))

        if content_length is None:
            raise ValueError("spamd response did not contain a Content-length header.")

        returned_message = self.reader.read(content_length)
        if len(returned_message) != content_length:
            raise ConnectionError("Could not read the full returned message from spamd.")

        return protocol_line, spamd_headers, returned_message

    def scan_email(self, message_bytes: bytes):
        """
        Sends one email to spamd and returns the parsed response parts.
        If the connection fails, the client reconnects once and retries.
        """
        request_bytes = self.build_request(message_bytes)

        for attempt in range(2):
            try:
                self.ensure_connected()
                self.sock.sendall(request_bytes)
                return self.read_response()
            except (OSError, ConnectionError, ValueError):
                self.close()
                if attempt == 1:
                    raise

        raise RuntimeError("Unexpected scan failure.")


def evaluate_email(
    client: SpamdClient,
    email_path: Path,
    dataset: str,
    label: str,
    message_id: str,
    variant_filename: str = "",
    salting_meta: dict | None = None,
):
    """
    Runs SpamAssassin on one email and returns a result row.
    For baseline emails, salting_meta is empty.
    For salted variants, salting_meta is taken from SALTING_LOG_CSV.
    """
    message_bytes = read_email_bytes(email_path)
    protocol_line, spamd_headers, returned_message = client.scan_email(message_bytes)

    parsed_msg = BytesParser(policy=policy.default).parsebytes(returned_message)
    x_spam_status = str(parsed_msg.get("X-Spam-Status", "")).replace("\n", " ").strip()
    spam_flag, score, threshold, rule_names = parse_x_spam_status(x_spam_status)

    salting_meta = salting_meta or {}
    n_insert_subject = salting_meta.get("n_insert_subject", "")
    n_insert_body = salting_meta.get("n_insert_body", "")

    return {
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
    }


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def run_spamassassin_evaluation(output_root=None, dataset_split_dir=None):
    """
    Runs the complete SpamAssassin evaluation.

    Workflow:
        - paired baseline spam test set
        - full baseline ham test set
        - salted spam variants
        - write variant-level results
        - write original-level paired results
    """

    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir

    RESULT_DIR = output_root / "spamassassin_evaluation"
    RESULT_CSV = RESULT_DIR / "spamassassin_results.csv"
    PAIRED_RESULT_CSV = RESULT_DIR / "spamassassin_results_paired.csv"

    SALTED_EMAILS_DIR = output_root / "salted_email_generator" / "emails"
    SALTING_LOG_CSV = output_root / "salted_email_generator" / "salting_log.csv"

    print_step("SpamAssassin Evaluation")

    test_spam_dir = dataset_split_dir / "test" / "spam"
    test_ham_dir = dataset_split_dir / "test" / "ham"

    salting_index = load_salting_log(SALTING_LOG_CSV)
    salted_source_ids = load_salted_source_ids(SALTING_LOG_CSV)

    spam_files = [
        p for p in sorted(test_spam_dir.iterdir())
        if p.is_file() and p.name in salted_source_ids
    ]
    ham_files = [p for p in sorted(test_ham_dir.iterdir()) if p.is_file()]
    salted_files = [p for p in sorted(SALTED_EMAILS_DIR.iterdir()) if p.is_file()]

    print_section("Evaluation dataset")
    print_kv("baseline_spam_paired", len(spam_files))
    print_kv("baseline_ham", len(ham_files))
    print_kv("salted_variants", len(salted_files))
    print_kv("salted_source_emails", len(salted_source_ids))

    results = []
    client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)

    try:
        print_section("Scanning emails")

        for path in tqdm(
            spam_files,
            desc="Baseline spam",
            unit="mail",
            colour="green",
            file=sys.stdout,
        ):
            results.append(
                evaluate_email(
                    client=client,
                    email_path=path,
                    dataset="baseline",
                    label="spam",
                    message_id=path.name,
                )
            )

        for path in tqdm(
            ham_files,
            desc="Baseline ham",
            unit="mail",
            colour="green",
            file=sys.stdout,
        ):
            results.append(
                evaluate_email(
                    client=client,
                    email_path=path,
                    dataset="baseline",
                    label="ham",
                    message_id=path.name,
                )
            )

        for path in tqdm(
            salted_files,
            desc="Salted spam",
            unit="mail",
            colour="green",
            file=sys.stdout,
        ):
            salting_meta = salting_index.get(path.name, {})

            results.append(
                evaluate_email(
                    client=client,
                    email_path=path,
                    dataset="salted",
                    label="spam",
                    message_id=salting_meta.get("message_id", ""),
                    variant_filename=path.name,
                    salting_meta=salting_meta,
                )
            )

    finally:
        client.close()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    with open(RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "label",
                "message_id",
                "variant_filename",
                "vocab_type",
                "codepoint",
                "salt_location",
                "n_insert_subject",
                "n_insert_body",
                "spam_flag",
                "score",
                "threshold",
                "rule_count",
                "rules",
                "protocol_line",
                "spamd_headers",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(results)

    paired_rows = build_paired_results(results)

    with open(PAIRED_RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "message_id",
                "baseline_score",
                "baseline_spam_flag",
                "baseline_rule_count",
                "n_variants",
                "salted_score_mean",
                "salted_score_min",
                "salted_score_max",
                "salted_rule_count_mean",
                "salted_any_spam",
                "salted_all_spam",
                "salted_any_bypass",
                "salted_all_bypass",
            ],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(paired_rows)

    print_section("Output files")
    print_kv("variant_results_csv", RESULT_CSV)
    print_kv("paired_results_csv", PAIRED_RESULT_CSV)

    print_end("SpamAssassin Evaluation")
