"""
Defines the Rspamd Bayes pilot cases and configured salting code point.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    PILOT_RS_BAYES_CODEPOINT_NAME,
    PILOT_RS_BAYES_CODEPOINT_CHAR,
)

CODEPOINT_NAME = PILOT_RS_BAYES_CODEPOINT_NAME
CODEPOINT_CHAR = PILOT_RS_BAYES_CODEPOINT_CHAR


@dataclass(frozen=True)
class RspamdBayesPilotCase:
    case_id: str
    title: str
    subject: str
    body: str
    notes: str = ""


RSB001 = RspamdBayesPilotCase(
    case_id="RSB01",
    title="Rspamd Bayes pilot mortgage spam case",
    subject="Hello Friend",
    body=(
        "Get your free mortgage rate quote now and see how much you could save every month!\n"
    ),
    notes=(
        "Pilot spam case based on a real mortgage quote spam email. "
        "Used for Rspamd Bayes evaluation with body-only ZWC salting."
    ),
)


BAYES_CASES: tuple[RspamdBayesPilotCase, ...] = (
    RSB001,
)


def get_rspamd_bayes_pilot_cases() -> list[RspamdBayesPilotCase]:
    return list(BAYES_CASES)