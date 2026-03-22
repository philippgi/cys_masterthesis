from __future__ import annotations

from dataclasses import dataclass


#CODEPOINT_NAME = "U+00AD"
#CODEPOINT_CHAR = "\u00ad"

CODEPOINT_NAME = "Random-String"
CODEPOINT_CHAR = "xyk"


@dataclass(frozen=True)
class RspamdBayesPilotCase:
    case_id: str
    title: str
    subject: str
    body: str
    notes: str = ""


RSB001 = RspamdBayesPilotCase(
    case_id="RSB001",
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