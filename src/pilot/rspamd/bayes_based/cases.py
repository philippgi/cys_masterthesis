from __future__ import annotations

from dataclasses import dataclass


CODEPOINT_NAME = "U+200B"
CODEPOINT_CHAR = "\u200b"


@dataclass(frozen=True)
class RspamdBayesPilotCase:
    case_id: str
    title: str
    subject: str
    body: str
    notes: str = ""


RSB001 = RspamdBayesPilotCase(
    case_id="RSB001",
    title="Rspamd Bayes pilot spam case",
    subject="Your devices were compromised",
    body=(
        "Hello,\n\n"
        "I know your password and I recorded you with your webcam.\n"
        "Do not try to ignore this message.\n"
        "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT within 48 hours.\n"
        "If you fail to comply, the material will be sent to your contacts.\n"
    ),
    notes=(
        "Single spam pilot case for Bayes discovery and paired evaluation. "
        "Discovery will identify candidate words by measuring Bayes score deltas "
        "after targeted zero-width salting."
    ),
)


BAYES_CASES: tuple[RspamdBayesPilotCase, ...] = (
    RSB001,
)


def get_rspamd_bayes_pilot_cases() -> list[RspamdBayesPilotCase]:
    return list(BAYES_CASES)