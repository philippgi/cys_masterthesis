from __future__ import annotations

from dataclasses import dataclass


CODEPOINT_NAME = "U+200B"
CODEPOINT_CHAR = "\u200b"


@dataclass(frozen=True)
class RspamdNeuralPilotCase:
    case_id: str
    title: str
    subject: str
    body: str
    notes: str = ""


RSN001 = RspamdNeuralPilotCase(
    case_id="RSN001",
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