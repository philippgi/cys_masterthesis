#!/usr/bin/env python3
"""
Evaluates baseline and salted email variants with SpamAssassin.

The runner scans paired baseline spam messages, the complete ham test set,
and all generated salted spam variants. Results are written at both the
variant level and the paired original-message level.
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
    Read a serialized RFC 5322 email message.

    Args:
        path (Path): Path to the email file.

    Returns:
        bytes: Raw message bytes.
    """

    return path.read_bytes()


def load_salting_log(csv_path: Path) -> dict[str, dict[str, str]]:
    """
    Load salting metadata indexed by salted variant filename.

    Args:
        csv_path (Path): Path to the salting log.

    Returns:
        dict[str, dict[str, str]]: Salting metadata indexed by variant filename.
    """

    if not csv_path.exists():
        return {}

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["variant_filename"]: row for row in reader}


def load_salted_source_ids(csv_path: Path) -> set[str]:
    """
    Load original message IDs for which salted variants were generated.

    Args:
        csv_path (Path): Path to the salting log.

    Returns:
        set[str]: Original message IDs represented in the salted dataset.
    """

    if not csv_path.exists():
        return set()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["message_id"] for row in reader if row.get("message_id")}


def derive_salt_location(n_insert_subject, n_insert_body) -> str:
    """
    Derive the salting location from Subject and body insertion counts.

    Args:
        n_insert_subject: Number of Subject insertions.
        n_insert_body: Number of body insertions.

    Returns:
        str: One of "subject", "body", "both", or "none".
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
    Parse classification data from the SpamAssassin X-Spam-Status header.

    Args:
        x_spam_status (str): X-Spam-Status header value.

    Returns:
        tuple: Spam flag, score, threshold, and triggered rule names.
    """

    if not x_spam_status:
        return False, None, None, []

    # Use SpamAssassin's own X-Spam-Status classification as the binary result.
    spam_flag = x_spam_status.lower().startswith("yes")

    # Extract score, threshold, and triggered rules from the returned header.
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
    Aggregate variant-level spam results on the original-message level.

    Each paired row combines one baseline spam email with all salted variants
    derived from that message.

    Args:
        rows (list[dict]): Variant-level evaluation results.

    Returns:
        list[dict]: Paired baseline and salted result rows.
    """

    baseline_by_message = {}
    salted_by_message = defaultdict(list)

    # Group baseline spam and salted variants by their original message ID.
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

        # Aggregate score, rule-count, and classification behavior across all salted variants.
        variant_scores = [v["score"] for v in variants if v["score"] is not None]
        variant_rule_counts = [v["rule_count"] for v in variants if v["rule_count"] is not None]
        variant_flags = [bool(v["spam_flag"]) for v in variants]

        # Derive Any/All spam and bypass outcomes on the original-message level.
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
    Maintain a reusable TCP connection to spamd.

    The client sends SPAMC HEADERS requests and reconnects once if a scan
    fails because the persistent connection was interrupted.
    """

    def __init__(self, host: str, port: int, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.reader = None

    def connect(self) -> None:
        """
        Open a TCP connection to spamd and prepare a buffered reader.
        """

        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self.reader = self.sock.makefile("rb")

    def close(self) -> None:
        """
        Close the current spamd connection and associated reader.
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
        Open a spamd connection if no active connection exists.
        """

        if self.sock is None or self.reader is None:
            self.connect()

    def build_request(self, message_bytes: bytes) -> bytes:
        """
        Build a SPAMC HEADERS request for one email message.

        Args:
            message_bytes (bytes): Serialized RFC 5322 message.

        Returns:
            bytes: Complete SPAMC request.
        """

        return (
            f"HEADERS SPAMC/1.5\r\n"
            f"Content-length: {len(message_bytes)}\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        ).encode("utf-8") + message_bytes

    def read_response(self):
        """
        Read and parse one complete spamd response.

        Returns:
            tuple: Protocol line, spamd response headers, and returned message bytes.

        Raises:
            ConnectionError: If the response is incomplete.
            ValueError: If Content-length is missing.
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
        Scan one email through spamd using the persistent connection.

        Args:
            message_bytes (bytes): Serialized RFC 5322 message.

        Returns:
            tuple: Parsed spamd response components.

        Raises:
            OSError: If both connection attempts fail.
            ConnectionError: If both response attempts fail.
            ValueError: If both responses are malformed.
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
    Scan one email and build its normalized variant-level result row.

    Args:
        client (SpamdClient): Connected spamd client.
        email_path (Path): Path to the email message.
        dataset (str): Dataset type, such as baseline or salted.
        label (str): Ground-truth class label.
        message_id (str): Original message identifier.
        variant_filename (str): Salted variant filename, if applicable.
        salting_meta (dict | None): Associated salting metadata.

    Returns:
        dict: Normalized SpamAssassin evaluation result.
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
    Run the complete SpamAssassin evaluation workflow.

    Args:
        output_root: Root directory for generated evaluation artifacts.
        dataset_split_dir: Directory containing the train/test dataset split.
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

    # Evaluate only baseline spam emails for which at least one salted variant exists.
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
