#!/usr/bin/env python3

"""
Orchestrates the illustrative email message processing pipeline.

The pipeline processes a serialized RFC 5322 email through six stages:
raw-byte inspection, MIME parsing, content-transfer decoding, charset
decoding, Unicode normalization, and tokenization.

Intermediate representations are printed to demonstrate how an inserted
zero-width Unicode character is represented throughout the processing
pipeline.
"""

import re
import sys

from src.email_pipeline.step1_raw import step1_read_raw_input
from src.email_pipeline.step2_mime import step2_parse_mime
from src.email_pipeline.step3_transfer import step3_transfer_decode_part
from src.email_pipeline.step4_charset import step4_charset_decode
from src.email_pipeline.step5_normalization import step5_normalize
from src.email_pipeline.step6_segmentation import step6_word_segmentation
from src.utils.console import print_step, print_section
from config import EML_PATH, BASE_DIR


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class Tee:
    """
    Mirrors stdout to the console and a log file.

    ANSI escape sequences are preserved for console output and removed
    from the log file.
    """

    def __init__(self, console_stream, file_stream):
        self.console_stream = console_stream
        self.file_stream = file_stream

    def write(self, data):
        self.console_stream.write(data)
        self.console_stream.flush()

        clean_data = ANSI_ESCAPE_RE.sub("", data)
        self.file_stream.write(clean_data)
        self.file_stream.flush()

    def flush(self):
        self.console_stream.flush()
        self.file_stream.flush()


def _run_pipeline_steps():
    """
    Execute the six message-processing stages in their defined order.

    Each stage receives the representation produced by the preceding
    stage and prints relevant intermediate results.
    """

    print_step("STEP 1: RAW INPUT")
    raw_bytes = step1_read_raw_input(EML_PATH)

    print_step("STEP 2: MIME PARSING + PART SELECTION")
    msg, text_part = step2_parse_mime(raw_bytes)

    print_step("STEP 3: CONTENT-TRANSFER DECODING (selected part)")
    decoded_bytes = step3_transfer_decode_part(text_part)

    print_step("STEP 4: CHARSET DECODING (declared charset)")
    unicode_text = step4_charset_decode(text_part, decoded_bytes)

    print_step("STEP 5: UNICODE NORMALIZATION")
    normalized_text = step5_normalize(unicode_text, apply_form="NFC")

    print_step("STEP 6: TOKENIZATION")
    _ = step6_word_segmentation(normalized_text)


def run_email_pipeline():
    """
    Run the email pipeline and write its console output to the pipeline log.
    """

    output_dir = BASE_DIR / "data/output/email_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / "pipeline_output.txt"

    original_stdout = sys.stdout

    with open(log_file, "w", encoding="utf-8") as file_handle:
        sys.stdout = Tee(original_stdout, file_handle)
        try:
            print_section("EMAIL PIPELINE RUN")
            print(f"Output file: {log_file}")
            _run_pipeline_steps()
        finally:
            sys.stdout = original_stdout


if __name__ == "__main__":
    run_email_pipeline()