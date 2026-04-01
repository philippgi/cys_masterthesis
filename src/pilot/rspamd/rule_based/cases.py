from __future__ import annotations

from dataclasses import dataclass


# --- Salting configuration (aligned with SpamAssassin pilot) ---
CODEPOINT_NAME = "U+200B"
CODEPOINT_CHAR = "\u200b"


@dataclass(frozen=True)
class RulePilotCase:
    case_id: str
    title: str
    expected_rule: str
    expected_behavior: str  # "break" or "preserve"
    subject: str
    body: str
    target_tokens_subject: tuple[str, ...] = ()
    target_tokens_body: tuple[str, ...] = ()
    notes: str = ""


# --- Pilot cases (Rspamd rules) ---
RULE_CASES: tuple[RulePilotCase, ...] = (

    # --- Subject rule: lexical / phrase-based ---
    RulePilotCase(
        case_id="RSR01",
        title="Break SUBJ_BOUNCE_WORDS via single U+200B insertion",
        expected_rule="SUBJ_BOUNCE_WORDS",
        expected_behavior="break",
        subject="Delivery failed: message could not be delivered",
        body="Hello,\nPlease see the details in the subject.\n",
        target_tokens_subject=("Delivery",),  # single controlled token
        notes="Lexical subject rule expected to break when token is salted.",
    ),

    # --- Body rule: sa_body selector ---
    RulePilotCase(
        case_id="RSR02",
        title="Test INTRODUCTION rule stability (sa_body selector)",
        expected_rule="INTRODUCTION",
        expected_behavior="preserve",
        subject="Project follow-up",
        body=(
            "Hello,\n\n"
            "My name is Mr Smith.\n"
            "I am contacting you regarding your recent inquiry.\n"
            "Please let me know if you need any additional details.\n"
        ),
        target_tokens_body=("name",),
        notes="Tests whether sa_body-based detection is robust against salting.",
    ),

    # --- Body rule: words selector (scam detection) ---
    RulePilotCase(
        case_id="RSR03",
        title="Test LEAKED_PASSWORD_SCAM with salted keyword",
        expected_rule="LEAKED_PASSWORD_SCAM",
        expected_behavior="preserve",
        subject="Your devices were compromised",
        body=(
            "Hello,\n\n"
            "I know your password and I recorded you with your webcam.\n"
            "Do not try to ignore this message.\n"
            "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT within 48 hours.\n"
            "If you fail to comply, the material will be sent to your contacts.\n"
        ),
        target_tokens_body=("webcam", "password", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT", "BTC"),
        notes="Composite rule using {words}; expected to be more robust.",
    ),

    # --- Control case (structural rule) ---
    RulePilotCase(
        case_id="RSR04",
        title="Control: SUBJ_ALL_CAPS should survive salting",
        expected_rule="SUBJ_ALL_CAPS",
        expected_behavior="preserve",
        subject="URGENT SECURITY NOTICE",
        body="This is a structural control case.\n",
        target_tokens_subject=("URGENT",),
        notes="Structural rule should not break under salting.",
    ),

RulePilotCase(
    case_id="RSR05",
    title="Mini-case: password + bitcoin address",
    expected_rule="LEAKED_PASSWORD_SCAM",
    expected_behavior="preserve",
    subject="Security notice",
    body=(
        "Hello,\n\n"
        "I know your password.\n"
        "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
    ),
    target_tokens_body=("password",),
    notes="Whitebox mini-case to test whether {words}-based password matching survives ZWC salting.",
),

RulePilotCase(
    case_id="RSR06",
    title="Mini-case: webcam + bitcoin address",
    expected_rule="LEAKED_PASSWORD_SCAM",
    expected_behavior="preserve",
    subject="Security notice",
    body=(
        "Hello,\n\n"
        "I recorded you with your webcam.\n"
        "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
    ),
    target_tokens_body=("webcam",),
    notes="Whitebox mini-case to test whether {words}-based webcam matching survives ZWC salting.",
),

RulePilotCase(
    case_id="RSR07",
    title="Mini-case: wallet + bitcoin address",
    expected_rule="LEAKED_PASSWORD_SCAM",
    expected_behavior="preserve",
    subject="Security notice",
    body=(
        "Hello,\n\n"
        "Your wallet is known to us.\n"
        "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
    ),
    target_tokens_body=("wallet",),
    notes="Whitebox mini-case to test whether {words}-based wallet matching survives ZWC salting.",
),

RulePilotCase(
    case_id="RSR08",
    title="Mini-case: victim + bitcoin address",
    expected_rule="LEAKED_PASSWORD_SCAM",
    expected_behavior="preserve",
    subject="Security notice",
    body=(
        "Hello,\n\n"
        "You are the victim.\n"
        "Send 0.5 BTC to 1BoatSLRHtKNngkdXEeobR76b53LETtpyT.\n"
    ),
    target_tokens_body=("victim", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"),
    notes="Whitebox mini-case to test whether {words}-based victim matching survives ZWC salting.",
),
RulePilotCase(
    case_id="RSR09",
    title="Mini-case: password without bitcoin address",
    expected_rule="LEAKED_PASSWORD_SCAM_RE",
    expected_behavior="preserve",
    subject="Security notice",
    body=(
        "Hello,\n\n"
        "I know your password.\n"
    ),
    target_tokens_body=("password",),
    notes="Whitebox mini-case to test whether the {words}-based password trigger is observable without the composite bitcoin dependency.",
),
)


def get_rule_pilot_cases() -> list[RulePilotCase]:
    return list(RULE_CASES)