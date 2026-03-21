from __future__ import annotations

import csv
import json
from pathlib import Path

from config import (
    PILOT_SALT_FRAGMENT_MAX_POSITIONS,
    PILOT_SALT_INSERT_AFTER_INDEX,
    PILOT_SALT_MODE,
    SALT_BODY_MAX_INSERTIONS,
    SALT_SUBJECT_MAX_INSERTIONS,
    SOCKET_TIMEOUT,
    SPAMD_HOST,
    SPAMD_PORT,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.salted_email_generator.generator import (
    apply_salting_to_message,
    parse_email,
    write_email,
)
from src.main_evaluation.spamassassin_evaluation.runner import SpamdClient
from src.pilot.spamassassin.bayes_based.bayes_cases import CODEPOINT_CHAR, CODEPOINT_NAME, SAB001
from src.pilot.spamassassin.bayes_based.bayes_runtime import (
    DISCOVERY_DIR,
    RESULTS_DIR,
    TEST_SALTED_DIR,
    TEST_UNSALTED_DIR,
    extract_bayes_rules,
    extract_rules,
    scan_email_with_details,
    wait_until_spamd_ready,
)
from src.utils.console import print_end, print_kv, print_section, print_step


def _write_csv(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_discovery() -> dict:
    json_path = DISCOVERY_DIR / f"{SAB001.case_id}_bayes_tokens_summary.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"Missing discovery output: {json_path}\n"
            "Run run_sa_pilot_bayes_discovery() first."
        )
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_salted_from_existing(
    unsalted_path: Path,
    salted_path: Path,
    target_tokens_subject: tuple[str, ...],
    target_tokens_body: tuple[str, ...],
    salt_mode: str,
    insert_after_index: int,
    fragment_max_positions: int | None,
) -> dict:
    original_msg, mbox_from_line = parse_email(unsalted_path)

    trigger_words = {token.lower() for token in list(target_tokens_subject) + list(target_tokens_body)}

    (
        salted_msg,
        subject_targets,
        body_targets,
        n_insert_subject,
        n_insert_body,
        body_part_found,
    ) = apply_salting_to_message(
        original_msg=original_msg,
        trigger_words=trigger_words,
        codepoint=CODEPOINT_CHAR,
        subject_max_insertions=SALT_SUBJECT_MAX_INSERTIONS,
        body_max_insertions=SALT_BODY_MAX_INSERTIONS,
        insert_after_index=insert_after_index,
        salt_mode=salt_mode,
        fragment_max_positions=fragment_max_positions,
    )

    salted_path.parent.mkdir(parents=True, exist_ok=True)
    write_email(salted_msg, salted_path, mbox_from_line=mbox_from_line)

    return {
        "n_insert_subject": n_insert_subject,
        "n_insert_body": n_insert_body,
        "salt_mode": salt_mode,
        "insert_after_index": insert_after_index,
        "fragment_max_positions": fragment_max_positions,
        "body_part_found": body_part_found,
        "subject_targets": subject_targets,
        "body_targets": body_targets,
    }


def run_sa_pilot_bayes_eval(
    salt_mode: str | None = None,
    insert_after_index: int | None = None,
    fragment_max_positions: int | None = None,
) -> None:
    print_step("SA Pilot - Bayes Eval")

    test_unsalted = TEST_UNSALTED_DIR / f"{SAB001.case_id}_unsalted.eml"
    test_salted = TEST_SALTED_DIR / f"{SAB001.case_id}_salted.eml"

    if not test_unsalted.exists():
        raise FileNotFoundError(
            f"Missing unsalted Bayes pilot mail: {test_unsalted}\n"
            "Run run_sa_pilot_bayes_prepare() first."
        )

    salt_mode = PILOT_SALT_MODE if salt_mode is None else salt_mode
    insert_after_index = (
        PILOT_SALT_INSERT_AFTER_INDEX if insert_after_index is None else insert_after_index
    )
    if salt_mode == "fragment":
        fragment_max_positions = (
            PILOT_SALT_FRAGMENT_MAX_POSITIONS
            if fragment_max_positions is None
            else fragment_max_positions
        )
    else:
        fragment_max_positions = None

    discovery = _load_discovery()
    target_tokens_subject = tuple(discovery.get("matched_tokens_subject", []))
    target_tokens_body = tuple(discovery.get("matched_tokens_body", []))

    counts = _build_salted_from_existing(
        unsalted_path=test_unsalted,
        salted_path=test_salted,
        target_tokens_subject=target_tokens_subject,
        target_tokens_body=target_tokens_body,
        salt_mode=salt_mode,
        insert_after_index=insert_after_index,
        fragment_max_positions=fragment_max_positions,
    )

    activate_spamassassin_config("sa_pilot_bayes.cf")
    restart_spamassassin()
    wait_until_spamd_ready(test_unsalted)

    client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)
    try:
        unsalted_scan = scan_email_with_details(
            client=client,
            email_path=test_unsalted,
            dataset="pilot",
            label="spam",
            message_id=SAB001.case_id,
            variant_filename=test_unsalted.name,
        )
        salted_scan = scan_email_with_details(
            client=client,
            email_path=test_salted,
            dataset="pilot",
            label="spam",
            message_id=SAB001.case_id,
            variant_filename=test_salted.name,
            salting_meta={
                "codepoint": CODEPOINT_NAME,
                "n_insert_subject": counts["n_insert_subject"],
                "n_insert_body": counts["n_insert_body"],
            },
        )
    finally:
        client.close()

    unsalted_row = unsalted_scan["row"]
    salted_row = salted_scan["row"]

    unsalted_rules = extract_rules(unsalted_row)
    salted_rules = extract_rules(salted_row)
    unsalted_bayes_rules = extract_bayes_rules(unsalted_rules)
    salted_bayes_rules = extract_bayes_rules(salted_rules)

    unsalted_spammy_tokens = unsalted_scan["spammy_tokens"]
    salted_spammy_tokens = salted_scan["spammy_tokens"]

    lost_spammy_tokens = [t for t in unsalted_spammy_tokens if t not in salted_spammy_tokens]
    new_rules = [r for r in salted_rules if r not in unsalted_rules]

    results_csv = RESULTS_DIR / "sa_pilot_bayes_results.csv"
    summary_json = RESULTS_DIR / "sa_pilot_bayes_summary.json"
    manifest_json = RESULTS_DIR / f"{SAB001.case_id}_salting_manifest.json"

    rows = [
        {
            "case_id": SAB001.case_id,
            "variant": "unsalted",
            "score": unsalted_row["score"],
            "spam_flag": unsalted_row["spam_flag"],
            "bayes_rules": "|".join(unsalted_bayes_rules),
            "spammy_tokens": "|".join(unsalted_spammy_tokens),
            "salt_mode": "",
            "n_insert_subject": "",
            "n_insert_body": "",
            "lost_spammy_tokens": "",
            "new_rules": "",
            "message_path": str(test_unsalted),
        },
        {
            "case_id": SAB001.case_id,
            "variant": "salted",
            "score": salted_row["score"],
            "spam_flag": salted_row["spam_flag"],
            "bayes_rules": "|".join(salted_bayes_rules),
            "spammy_tokens": "|".join(salted_spammy_tokens),
            "salt_mode": salt_mode,
            "n_insert_subject": counts["n_insert_subject"],
            "n_insert_body": counts["n_insert_body"],
            "lost_spammy_tokens": "|".join(lost_spammy_tokens),
            "new_rules": "|".join(new_rules),
            "message_path": str(test_salted),
        },
    ]

    summary = {
        "case_id": SAB001.case_id,
        "title": SAB001.title,
        "salted_target_tokens_subject": list(target_tokens_subject),
        "salted_target_tokens_body": list(target_tokens_body),
        "salt_mode": salt_mode,
        "insert_after_index": insert_after_index,
        "fragment_max_positions": fragment_max_positions,
        "n_insert_subject": counts["n_insert_subject"],
        "n_insert_body": counts["n_insert_body"],
        "unsalted_score": unsalted_row["score"],
        "salted_score": salted_row["score"],
        "unsalted_bayes_rules": unsalted_bayes_rules,
        "salted_bayes_rules": salted_bayes_rules,
        "unsalted_spammy_tokens": unsalted_spammy_tokens,
        "salted_spammy_tokens": salted_spammy_tokens,
        "lost_spammy_tokens": lost_spammy_tokens,
        "new_rules": new_rules,
    }

    manifest = {
        "case_id": SAB001.case_id,
        "codepoint": CODEPOINT_NAME,
        "target_tokens_subject": list(target_tokens_subject),
        "target_tokens_body": list(target_tokens_body),
        "salt_mode": salt_mode,
        "insert_after_index": insert_after_index,
        "fragment_max_positions": fragment_max_positions,
        "n_insert_subject": counts["n_insert_subject"],
        "n_insert_body": counts["n_insert_body"],
        "subject_targets": counts["subject_targets"],
        "body_targets": counts["body_targets"],
        "body_part_found": counts["body_part_found"],
    }

    _write_csv(results_csv, rows)
    _write_json(summary_json, summary)
    _write_json(manifest_json, manifest)

    print_section("Unsalted")
    print_kv("score", unsalted_row["score"])
    print_kv("bayes_rules", unsalted_bayes_rules)
    print_kv("spammy_tokens", unsalted_spammy_tokens)

    print_section("Salted")
    print_kv("score", salted_row["score"])
    print_kv("bayes_rules", salted_bayes_rules)
    print_kv("spammy_tokens", salted_spammy_tokens)
    print_kv("lost_spammy_tokens", lost_spammy_tokens)
    print_kv("new_rules", new_rules)

    print_section("Salting")
    print_kv("target_tokens_subject", list(target_tokens_subject))
    print_kv("target_tokens_body", list(target_tokens_body))
    print_kv("salt_mode", salt_mode)
    print_kv(
        "insertions",
        {
            "n_insert_subject": counts["n_insert_subject"],
            "n_insert_body": counts["n_insert_body"],
        },
    )

    print_end("SA Pilot - Bayes Eval")
