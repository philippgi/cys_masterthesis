from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from config import BASE_DIR
from src.utils.console import print_step, print_end


TEST_UNSALTED_DIR = BASE_DIR / "data/output/pilot/sa/bayes/test_unsalted"


def build_message_bytes(subject: str, body: str, from_addr: str, to_addr: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="pilot.example.test")
    msg.set_content(body)
    return msg.as_bytes()


def write_message(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def run_sa_pilot_bayes_prepare() -> None:
    print_step("SA Pilot - Bayes Prepare")

    subject = "Security verification notice"
    body = (
        "Your account security requires verification.\n"
        "Verify your account password and login information now."
    )

    msg_bytes = build_message_bytes(
        subject=subject,
        body=body,
        from_addr="pilot-test@example.test",
        to_addr="victim@example.test",
    )

    output_path = TEST_UNSALTED_DIR / "SAB001_unsalted.eml"
    write_message(output_path, msg_bytes)

    print_end("SA Pilot - Bayes Prepare")
