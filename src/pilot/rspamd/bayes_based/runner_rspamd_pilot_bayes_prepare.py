#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

from config import BASE_DIR
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.pilot.rspamd.bayes_based.cases import BAYES_CASES, CODEPOINT_CHAR
from src.pilot.rspamd.rule_based.template_builder import create_paired_bytes, write_message
from src.utils.console import print_step, print_section, print_kv, print_end


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/rspamd/bayes"
TEST_UNSALTED_DIR = OUTPUT_ROOT / "messages" / "unsalted"


def run_rspamd_pilot_bayes_prepare() -> None:
    print_step("Rspamd Pilot - Bayes Prepare")

    case = BAYES_CASES[0]

    activate_rspamd_config("rs_pilot_bayes")
    restart_rspamd()
    time.sleep(5)

    print_section("Pilot case")
    print_kv("case_id", case.case_id)
    print_kv("title", case.title)

    unsalted_bytes, _, _ = create_paired_bytes(
        subject=case.subject,
        body=case.body,
        target_tokens_subject=(),
        target_tokens_body=(),
        codepoint=CODEPOINT_CHAR,
        from_addr="pilot@example.test",
        to_addr="victim@example.test",
    )

    unsalted_path = TEST_UNSALTED_DIR / f"{case.case_id}_unsalted.eml"
    write_message(unsalted_path, unsalted_bytes)

    print_section("Prepared files")
    print_kv("unsalted_mail", unsalted_path)

    print_end("Rspamd Pilot - Bayes Prepare")


if __name__ == "__main__":
    run_rspamd_pilot_bayes_prepare()