from __future__ import annotations

from dataclasses import dataclass


CODEPOINT_NAME = "U+200B"
CODEPOINT_CHAR = "\u200b"


@dataclass(frozen=True)
class SARuleCase:
    case_id: str
    title: str
    subject: str
    body: str
    target_tokens_subject: tuple[str, ...]
    target_tokens_body: tuple[str, ...]
    expected_rule: str
    expected_behavior: str = "break"


SAR001 = SARuleCase(
    case_id="SAR001",
    title="Break SUBJ_YOUR_FAMILY with a single U+200B insertion",
    subject="Your Family needs your attention",
    body="Hello,\nthis is a synthetic pilot message.\n",
    target_tokens_subject=("Family",),
    target_tokens_body=(),
    expected_rule="SUBJ_YOUR_FAMILY",
)

SAR002 = SARuleCase(
    case_id="SAR002",
    title="Break SUBJ_AS_SEEN with a single U+200B insertion",
    subject="As Seen on TV",
    body="Hello,\nthis is a synthetic pilot message.\n",
    target_tokens_subject=("Seen",),
    target_tokens_body=(),
    expected_rule="SUBJ_AS_SEEN",
)

SAR003 = SARuleCase(
    case_id="SAR003",
    title="Break TVD_PH_SEC with a single U+200B insertion",
    subject="Security notice",
    body="Your account security requires verification.\n",
    target_tokens_subject=(),
    target_tokens_body=("account",),
    expected_rule="TVD_PH_SEC",
)

SAR004 = SARuleCase(
    case_id="SAR004",
    title="Break TVD_PH_REC with a single U+200B insertion",
    subject="Account record notice",
    body="Your account record requires review.\n",
    target_tokens_subject=(),
    target_tokens_body=("account",),
    expected_rule="TVD_PH_REC",
)

SAR005 = SARuleCase(
    case_id="SAR005",
    title="Control case: SUBJ_ALL_CAPS should survive a single U+200B insertion",
    subject="URGENT SECURITY NOTICE",
    body="This is a structural control case.\n",
    target_tokens_subject=("URGENT",),
    target_tokens_body=(),
    expected_rule="SUBJ_ALL_CAPS",
    expected_behavior="preserve",
)


RULE_CASES: tuple[SARuleCase, ...] = (
    SAR001,
    SAR002,
    SAR003,
    SAR004,
    SAR005,
)