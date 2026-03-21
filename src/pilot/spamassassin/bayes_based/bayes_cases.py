from __future__ import annotations

from dataclasses import dataclass


CODEPOINT_NAME = "U+200B"
CODEPOINT_CHAR = "\u200b"


@dataclass(frozen=True)
class SABayesCase:
    case_id: str
    title: str
    subject: str
    body: str
    from_addr: str = "pilot-test@example.test"
    to_addr: str = "victim@example.test"


SAB001 = SABayesCase(
    case_id="SAB001",
    title="Bayes signal reduction for verify-account-security vocabulary",
    subject="Security verification notice",
    body=(
        "Your account security requires verification.\n"
        "Verify your account password and login information now.\n"
    ),
)
