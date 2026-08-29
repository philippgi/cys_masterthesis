"""
Defines the SpamAssassin Bayes pilot case and salting code point.

The curated case provides the message content used for Bayes token discovery
and subsequent paired salting evaluation.
"""

from __future__ import annotations

from config import PILOT_SA_BAYES_CODEPOINT_CHAR, PILOT_SA_BAYES_CODEPOINT_NAME

CODEPOINT_CHAR = PILOT_SA_BAYES_CODEPOINT_CHAR
CODEPOINT_NAME = PILOT_SA_BAYES_CODEPOINT_NAME


class SABayesCase:
    """
    Represent a synthetic SpamAssassin Bayes pilot case.
    """
    def __init__(self, case_id: str, title: str, subject: str, body: str):
        self.case_id = case_id
        self.title = title
        self.subject = subject
        self.body = body


SAB001 = SABayesCase(
    case_id="SAB001",
    title="Basic verification mail",
    subject="Security verification notice",
    body=(
        "Your account security requires verification.\n"
        "Verify your account password and login information now."
    ),
)
