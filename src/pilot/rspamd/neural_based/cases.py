"""
Defines the Rspamd neural pilot cases and configured salting code point.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    PILOT_RS_NEURAL_CODEPOINT_NAME,
    PILOT_RS_NEURAL_CODEPOINT_CHAR,
)

CODEPOINT_NAME = PILOT_RS_NEURAL_CODEPOINT_NAME
CODEPOINT_CHAR = PILOT_RS_NEURAL_CODEPOINT_CHAR


@dataclass(frozen=True)
class RspamdNeuralPilotCase:
    case_id: str
    title: str
    subject: str
    body: str
    notes: str = ""


RSN001 = RspamdNeuralPilotCase(
    case_id="RSN01",
    title="Rspamd Neural pilot mortgage spam case",
    subject="Hello Martin",
    body=(
        "Did you hear? Interest rates have just been lowered again. Don't delay! "
    ),
    notes="Pilot spam case for Rspamd Neural evaluation with body-only salting.",
)


NEURAL_CASES: tuple[RspamdNeuralPilotCase, ...] = (
    RSN001,
)


def get_rspamd_neural_pilot_cases() -> list[RspamdNeuralPilotCase]:
    return list(NEURAL_CASES)