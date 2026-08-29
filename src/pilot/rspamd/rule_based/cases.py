"""
Defines the rule-based Rspamd pilot cases.

Each case specifies the targeted rule, expected behavior, selector context,
salting targets, and metadata used during pilot message generation and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from config import PILOT_RS_RULE_CODEPOINT_CHAR, PILOT_RS_RULE_CODEPOINT_NAME


CODEPOINT_NAME = PILOT_RS_RULE_CODEPOINT_NAME
CODEPOINT_CHAR = PILOT_RS_RULE_CODEPOINT_CHAR


@dataclass(frozen=True)
class RulePilotCase:
    case_id: str
    title: str
    expected_rule: str
    expected_behavior: str
    rule_type: str
    rule_family: str
    selector_type: str
    discovered_via: str
    selection_rationale: str
    subject: str
    body: str
    target_tokens_subject: tuple[str, ...] = ()
    target_tokens_body: tuple[str, ...] = ()
    notes: str = ""


RULE_CASES: tuple[RulePilotCase, ...] = (

    # ============================================================
    # HEADER / SUBJECT
    # ============================================================
    RulePilotCase(
        case_id="RSR01",
        title="SUBJ_BOUNCE_WORDS",
        expected_rule="SUBJ_BOUNCE_WORDS",
        expected_behavior="break",
        rule_type="header",
        rule_family="header",
        selector_type="header",
        discovered_via="rule_discovery + whitebox validation",
        selection_rationale=(
            "Selected because it is a visible, attacker-controlled subject rule "
            "based on lexical bounce keywords and can be targeted directly with ZWC salting."
        ),
        subject="Delivery failed: message could not be delivered",
        body="Hello,\nPlease see the details in the subject.\n",
        target_tokens_subject=("Delivery",),
        notes=(
            "Strong break candidate. Already observed to trigger unsalted and break after salting."
        ),
    ),

    RulePilotCase(
        case_id="RSR02",
        title="SUBJ_ALL_CAPS",
        expected_rule="SUBJ_ALL_CAPS",
        expected_behavior="break",
        rule_type="header",
        rule_family="header",
        selector_type="header",
        discovered_via="whitebox design",
        selection_rationale=(
            "Selected as a visible-content control case to test whether a more structural "
            "subject-level heuristic remains stable under token salting."
        ),
        subject="URGENT SECURITY NOTICE",
        body="This is a structural control case.\n",
        target_tokens_subject=("URGENT",),
        notes=(
            "Control case. Keep only if SUBJ_ALL_CAPS is actually emitted in your current config."
        ),
    ),

    # ============================================================
    # BODY_SA_BODY
    # ============================================================
    RulePilotCase(
        case_id="RSR03",
        title="Test INTRODUCTION rule",
        expected_rule="INTRODUCTION",
        expected_behavior="preserve",
        rule_type="body_sa_body",
        rule_family="body_sa_body",
        selector_type="sa_body",
        discovered_via="rule_discovery + whitebox validation",
        selection_rationale=(
            "Selected because the rule pattern is based on visible introductory body text "
            "and is suitable as a robustness case for normalized body matching."
        ),
        subject="Project follow-up",
        body=(
            "Hello,\n\n"
            "My name is Mr Smith.\n"
            "I am contacting you regarding your recent inquiry.\n"
            "Please let me know if you need any additional details.\n"
        ),
        target_tokens_body=("My", "name", "is", "Mr"),
        notes=(
            "Good preserve/robustness case. In previous run, unsalted and salted both hit."
        ),
    ),

    # ============================================================
    # BODY_WORDS / COMPOSITE SCAM
    # ============================================================
    RulePilotCase(
        case_id="RSR04",
        title="password + bitcoin address",
        expected_rule="LEAKED_PASSWORD_SCAM",
        expected_behavior="preserve",
        rule_type="body_words",
        rule_family="body_words",
        selector_type="words",
        discovered_via="whitebox validation",
        selection_rationale=(
            "Selected as a reduced visible-content variant to isolate the contribution of the "
            "'password' token within the scam rule family."
        ),
        subject="Security notice",
        body=(
            "Hello,\n\n"
            "I know your password.\n"
            "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
        ),
        target_tokens_body=("password", "BTC", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"),
        notes=(
            "Useful mini-case if the composite rule is triggered by password + wallet/payment indicator."
        ),
    ),

    RulePilotCase(
        case_id="RSR05",
        title="victim + bitcoin address",
        expected_rule="LEAKED_PASSWORD_SCAM",
        expected_behavior="preserve",
        rule_type="body_words",
        rule_family="body_words",
        selector_type="words",
        discovered_via="whitebox validation",
        selection_rationale=(
            "Selected as a reduced visible-content variant to isolate the contribution of the "
            "'victim' token within the scam rule family."
        ),
        subject="Security notice",
        body=(
            "Hello,\n\n"
            "You are the victim.\n"
            "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
        ),
        target_tokens_body=("victim", "BTC", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"),
        notes=(
            "Useful mini-case if victim participates directly in the matched word set."
        ),
    ),
)


def get_rule_pilot_cases() -> list[RulePilotCase]:
    return list(RULE_CASES)