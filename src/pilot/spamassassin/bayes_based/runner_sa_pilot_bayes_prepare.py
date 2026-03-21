from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from src.pilot.spamassassin.bayes_based.bayes_cases import SAB001
from src.pilot.spamassassin.bayes_based.bayes_runtime import (
    DISCOVERY_DIR,
    RESULTS_DIR,
    TEST_SALTED_DIR,
    TEST_UNSALTED_DIR,
)
from src.utils.console import print_end, print_kv, print_step


SUBJECT = "Security verification notice"
BODY = (
    "Your account security requires verification.\n"
    "Verify your account password and login information now."
)
FROM_ADDR = "pilot-test@example.test"
TO_ADDR = "victim@example.test"


def run_sa_pilot_bayes_prepare() -> None:
    print_step("SA Pilot - Bayes Prepare")

    msg = EmailMessage()
    msg["From"] = FROM_ADDR
    msg["To"] = TO_ADDR
    msg["Subject"] = SUBJECT
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="pilot.example.test")
    msg.set_content(BODY)

    unsalted_path = TEST_UNSALTED_DIR / f"{SAB001.case_id}_unsalted.eml"
    salted_path = TEST_SALTED_DIR / f"{SAB001.case_id}_salted.eml"
    discovery_json = DISCOVERY_DIR / f"{SAB001.case_id}_bayes_tokens_summary.json"
    discovery_csv = DISCOVERY_DIR / f"{SAB001.case_id}_bayes_tokens.csv"
    results_csv = RESULTS_DIR / "sa_pilot_bayes_results.csv"
    results_json = RESULTS_DIR / "sa_pilot_bayes_summary.json"
    manifest_json = RESULTS_DIR / f"{SAB001.case_id}_salting_manifest.json"

    unsalted_path.parent.mkdir(parents=True, exist_ok=True)
    unsalted_path.write_bytes(msg.as_bytes())

    for path in [salted_path, discovery_json, discovery_csv, results_csv, results_json, manifest_json]:
        if path.exists():
            path.unlink()

    print_kv("unsalted_mail", unsalted_path)
    print_end("SA Pilot - Bayes Prepare")
