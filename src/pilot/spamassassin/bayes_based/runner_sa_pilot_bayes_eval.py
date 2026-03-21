from __future__ import annotations

import socket
import time
from pathlib import Path

from config import (
    BASE_DIR,
    PILOT_SALT_FRAGMENT_MAX_POSITIONS,
    PILOT_SALT_INSERT_AFTER_INDEX,
    PILOT_SALT_MODE,
    SALT_BODY_MAX_INSERTIONS,
    SALT_SUBJECT_MAX_INSERTIONS,
    SPAMD_HOST,
    SPAMD_PORT,
    SOCKET_TIMEOUT,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.salted_email_generator.generator import (
    apply_salting_to_message,
    parse_email,
    write_email,
)
from src.main_evaluation.spamassassin_evaluation.runner import SpamdClient
from src.pilot.spamassassin.bayes_based.bayes_cases import CODEPOINT_CHAR
from src.utils.console import print_end, print_kv, print_section, print_step


BASE = BASE_DIR / "data/output/pilot/sa/bayes"
TEST_UNSALTED = BASE / "test_unsalted" / "SAB001_unsalted.eml"
TEST_SALTED = BASE / "test_salted" / "SAB001_salted.eml"


def wait_until_spamd_ready():
    for _ in range(20):
        try:
            with socket.create_connection((SPAMD_HOST, SPAMD_PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("spamd not ready")


def run_sa_pilot_bayes_eval():
    print_step("SA Pilot - Bayes Eval")

    activate_spamassassin_config("sa_pilot_bayes.cf")
    restart_spamassassin()
    wait_until_spamd_ready()

    client = SpamdClient(SPAMD_HOST, SPAMD_PORT, SOCKET_TIMEOUT)

    try:
        unsalted = client.check_file(TEST_UNSALTED)

        original_msg, mbox = parse_email(TEST_UNSALTED)

        salted_msg, *_ = apply_salting_to_message(
            original_msg=original_msg,
            trigger_words=set(unsalted.get("spammy_tokens", [])),
            codepoint=CODEPOINT_CHAR,
            subject_max_insertions=SALT_SUBJECT_MAX_INSERTIONS,
            body_max_insertions=SALT_BODY_MAX_INSERTIONS,
            insert_after_index=PILOT_SALT_INSERT_AFTER_INDEX,
            salt_mode=PILOT_SALT_MODE,
            fragment_max_positions=PILOT_SALT_FRAGMENT_MAX_POSITIONS,
        )

        TEST_SALTED.parent.mkdir(parents=True, exist_ok=True)
        write_email(salted_msg, TEST_SALTED, mbox_from_line=mbox)

        salted = client.check_file(TEST_SALTED)

    finally:
        client.close()

    unsalted_tokens = unsalted.get("spammy_tokens", [])
    salted_tokens = salted.get("spammy_tokens", [])

    lost = [t for t in unsalted_tokens if t not in salted_tokens]

    print_section("Unsalted")
    print_kv("score", unsalted.get("score"))
    print_kv("tokens", unsalted_tokens)

    print_section("Salted")
    print_kv("score", salted.get("score"))
    print_kv("tokens", salted_tokens)
    print_kv("lost_tokens", lost)

    print_end("SA Pilot - Bayes Eval")
