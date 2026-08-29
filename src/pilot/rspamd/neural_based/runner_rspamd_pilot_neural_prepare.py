#!/usr/bin/env python3
"""
Prepares the unsalted message used for the Rspamd neural pilot evaluation.
"""

from __future__ import annotations

import time

from config import (
    PILOT_RS_NEURAL_OUTPUT_DIR,
    PILOT_RS_NEURAL_CONFIG_NAME,
    PILOT_RS_NEURAL_READY_SLEEP_SECONDS,
    PILOT_RS_NEURAL_FROM_ADDR,
    PILOT_RS_NEURAL_TO_ADDR,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.pilot.rspamd.neural_based.cases import NEURAL_CASES, CODEPOINT_CHAR
from src.pilot.rspamd.neural_based.template_builder_neural import create_paired_bytes, write_message
from src.utils.console import print_step, print_section, print_kv, print_end


OUTPUT_ROOT = PILOT_RS_NEURAL_OUTPUT_DIR
TEST_UNSALTED_DIR = OUTPUT_ROOT / "messages" / "unsalted"


def run_rspamd_pilot_neural_prepare() -> None:
    """
    Activate the pilot configuration and create the unsalted pilot message.
    """

    print_step("Rspamd Pilot - Neural Prepare")

    case = NEURAL_CASES[0]

    activate_rspamd_config(PILOT_RS_NEURAL_CONFIG_NAME)
    restart_rspamd()
    time.sleep(PILOT_RS_NEURAL_READY_SLEEP_SECONDS)

    print_section("Pilot case")
    print_kv("case_id", case.case_id)
    print_kv("title", case.title)

    unsalted_bytes, _, _ = create_paired_bytes(
        subject=case.subject,
        body=case.body,
        target_tokens_subject=(),
        target_tokens_body=(),
        codepoint=CODEPOINT_CHAR,
        from_addr=PILOT_RS_NEURAL_FROM_ADDR,
        to_addr=PILOT_RS_NEURAL_TO_ADDR,
    )

    unsalted_path = TEST_UNSALTED_DIR / f"{case.case_id}_unsalted.eml"
    write_message(unsalted_path, unsalted_bytes)

    print_section("Prepared files")
    print_kv("unsalted_mail", unsalted_path)

    print_end("Rspamd Pilot - Neural Prepare")


if __name__ == "__main__":
    run_rspamd_pilot_neural_prepare()