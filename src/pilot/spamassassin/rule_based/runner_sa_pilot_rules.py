"""
Runs the rule-based SpamAssassin pilot evaluation.

For each configured pilot case, paired unsalted and salted messages are
generated, scanned with SpamAssassin, and compared with respect to the
targeted rule, score, and expected rule behavior.
"""

from __future__ import annotations

import time
from pathlib import Path

from config import (
    PILOT_SA_RULE_CONFIG_NAME,
    PILOT_SA_RULE_FROM_ADDR,
    PILOT_SA_RULE_OUTPUT_DIR,
    PILOT_SA_RULE_READY_POLL_INTERVAL,
    PILOT_SA_RULE_READY_TIMEOUT_SECONDS,
    PILOT_SA_RULE_TO_ADDR,
    SOCKET_TIMEOUT,
    SPAMD_HOST,
    SPAMD_PORT,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.spamassassin_evaluation.runner import SpamdClient, evaluate_email
from src.pilot.spamassassin.rule_based.cases import CODEPOINT_CHAR, CODEPOINT_NAME, RULE_CASES
from src.pilot.spamassassin.rule_based.template_builder import create_paired_bytes, write_message
from src.pilot.spamassassin.summary import write_csv, write_json


OUTPUT_ROOT = PILOT_SA_RULE_OUTPUT_DIR


def wait_until_spamd_ready(
    probe_path: Path,
    timeout_seconds: int = PILOT_SA_RULE_READY_TIMEOUT_SECONDS,
    poll_interval: float = PILOT_SA_RULE_READY_POLL_INTERVAL,
) -> None:
    """
    Wait until spamd successfully evaluates a probe message.

    Args:
        probe_path (Path): Message used for readiness checks.
        timeout_seconds (int): Maximum waiting period in seconds.
        poll_interval (float): Delay between consecutive checks.

    Raises:
        TimeoutError: If spamd does not become ready within the timeout.
    """

    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)
        try:
            evaluate_email(
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


def run_sa_pilot_rules() -> None:
    """
    Execute all configured rule-based SpamAssassin pilot cases and save the results.
    """

    print("=== SA Pilot: rule cases ===")

    activate_spamassassin_config(PILOT_SA_RULE_CONFIG_NAME)
    restart_spamassassin()

    # Use a temporary probe message to verify that spamd is reachable after restart.
    probe_case = RULE_CASES[0]
    probe_unsalted_bytes, _, _ = create_paired_bytes(
        subject=probe_case.subject,
        body=probe_case.body,
        target_tokens_subject=probe_case.target_tokens_subject,
        target_tokens_body=probe_case.target_tokens_body,
        codepoint=CODEPOINT_CHAR,
        from_addr=PILOT_SA_RULE_FROM_ADDR,
        to_addr=PILOT_SA_RULE_TO_ADDR,
    )
    probe_path = OUTPUT_ROOT / "messages" / "unsalted" / "_probe.eml"
    write_message(probe_path, probe_unsalted_bytes)

    wait_until_spamd_ready(probe_path)

    if probe_path.exists():
        probe_path.unlink()

    results_csv = OUTPUT_ROOT / "results" / "sa_pilot_rules_results.csv"
    summary_json = OUTPUT_ROOT / "results" / "sa_pilot_rules_summary.json"

    rows: list[dict] = []
    paired_summary: list[dict] = []

    client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)

    try:
        for case in RULE_CASES:
            print()
            print("Case:", case.case_id)
            print("Expected rule:", case.expected_rule)

            unsalted_bytes, salted_bytes, counts = create_paired_bytes(
                subject=case.subject,
                body=case.body,
                target_tokens_subject=case.target_tokens_subject,
                target_tokens_body=case.target_tokens_body,
                codepoint=CODEPOINT_CHAR,
                from_addr=PILOT_SA_RULE_FROM_ADDR,
                to_addr=PILOT_SA_RULE_TO_ADDR,
            )

            unsalted_path = OUTPUT_ROOT / "messages" / "unsalted" / f"{case.case_id}_unsalted.eml"
            salted_path = OUTPUT_ROOT / "messages" / "salted" / f"{case.case_id}_salted.eml"

            write_message(unsalted_path, unsalted_bytes)
            write_message(salted_path, salted_bytes)

            unsalted_row = evaluate_email(
                client=client,
                email_path=unsalted_path,
                dataset="pilot",
                label="spam",
                message_id=case.case_id,
                variant_filename=unsalted_path.name,
                salting_meta={},
            )

            salted_row = evaluate_email(
                client=client,
                email_path=salted_path,
                dataset="pilot",
                label="spam",
                message_id=case.case_id,
                variant_filename=salted_path.name,
                salting_meta={
                    "codepoint": CODEPOINT_NAME,
                    "n_insert_subject": counts["n_insert_subject"],
                    "n_insert_body": counts["n_insert_body"],
                },
            )

            # Normalize the reported rule list and ignore score fragments such as RULE=score.
            unsalted_rules = [
                r.strip()
                for r in str(unsalted_row["rules"]).split("|")
                if r.strip() and "=" not in r
            ]
            salted_rules = [
                r.strip()
                for r in str(salted_row["rules"]).split("|")
                if r.strip() and "=" not in r
            ]

            unsalted_hit = case.expected_rule in unsalted_rules
            salted_hit = case.expected_rule in salted_rules
            break_success = unsalted_hit and not salted_hit

            # Evaluate success according to the expected behavior of the current pilot case.
            if case.expected_behavior == "preserve":
                case_success = unsalted_hit and salted_hit
            else:
                case_success = break_success

            rows.extend(
                [
                    {
                        "case_id": case.case_id,
                        "title": case.title,
                        "variant": "unsalted",
                        "expected_rule": case.expected_rule,
                        "spam_flag": unsalted_row["spam_flag"],
                        "score": unsalted_row["score"],
                        "rules": "|".join(unsalted_rules),
                        "expected_rule_hit": unsalted_hit,
                        "n_insert_subject": 0,
                        "n_insert_body": 0,
                        "message_path": str(unsalted_path),
                        "expected_behavior": case.expected_behavior,
                        "break_success": break_success,
                        "case_success": case_success,
                    },
                    {
                        "case_id": case.case_id,
                        "title": case.title,
                        "variant": "salted",
                        "expected_rule": case.expected_rule,
                        "spam_flag": salted_row["spam_flag"],
                        "score": salted_row["score"],
                        "rules": "|".join(salted_rules),
                        "expected_rule_hit": salted_hit,
                        "n_insert_subject": counts["n_insert_subject"],
                        "n_insert_body": counts["n_insert_body"],
                        "message_path": str(salted_path),
                        "expected_behavior": case.expected_behavior,
                        "break_success": break_success,
                        "case_success": case_success,
                    },
                ]
            )

            paired_summary.append(
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "expected_rule": case.expected_rule,
                    "expected_behavior": case.expected_behavior,
                    "unsalted_rules": unsalted_rules,
                    "salted_rules": salted_rules,
                    "unsalted_hit": unsalted_hit,
                    "salted_hit": salted_hit,
                    "break_success": break_success,
                    "case_success": case_success,
                    "unsalted_score": unsalted_row["score"],
                    "salted_score": salted_row["score"],
                }
            )

            print("Unsalted subject:", case.subject)
            print("Insertions:", counts)
            print("\n--- Unsalted ---")
            print("spam_flag:", unsalted_row["spam_flag"])
            print("score:", unsalted_row["score"])
            print("rules:", "|".join(unsalted_rules))
            print("\n--- Salted ---")
            print("spam_flag:", salted_row["spam_flag"])
            print("score:", salted_row["score"])
            print("rules:", "|".join(salted_rules))
            print("\n--- Rule comparison ---")
            print("expected_rule:", case.expected_rule)
            print("unsalted_hit:", unsalted_hit)
            print("salted_hit:", salted_hit)
            print("break_success:", break_success)
            print("case_success:", case_success)

    finally:
        client.close()

    write_csv(results_csv, rows)
    write_json(summary_json, {"paired_summary": paired_summary})

    print()
    print("Saved:")
    print(results_csv)
    print(summary_json)


if __name__ == "__main__":
    run_sa_pilot_rules()
