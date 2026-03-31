#!/usr/bin/env python3

"""
Main - Practical Email Message Representation Pipeline

This script orchestrates the steps for processing an email message on the receiver side, starting from the raw RFC5322
byte stream and ending with a tokenized text representation.

Each step in the pipeline performs a well-defined transformation of the message representation:
- Step 1: Raw message bytes
- Step 2: Structured MIME message and part selection
- Step 3: Content-Transfer-Decoding (bytes)
- Step 4: Charset decoding (Unicode text)
- Step 5: Unicode normalization (canonical text)
- Step 6: Tokenization (word-like units)

The pipeline is designed as an proof-of-concept to demonstrate that zero-width Unicode characters can survive common
preprocessing stages and become semantically relevant only at the tokenization stage.
"""

import re
import sys

from src.email_pipeline.step1_raw import step1_read_raw_input
from src.email_pipeline.step2_mime import step2_parse_mime
from src.email_pipeline.step3_transfer import step3_transfer_decode_part
from src.email_pipeline.step4_charset import step4_charset_decode
from src.email_pipeline.step5_normalization import step5_normalize
from src.email_pipeline.step6_segmentation import step6_word_segmentation
from config import EML_PATH, BASE_DIR
from src.utils.console import print_step, print_section


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class Tee:
    """
    Writes stdout simultaneously to console and file.
    ANSI escape sequences are preserved for console output
    but removed from the log file.
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
    Execute the complete message representation pipeline in a linear, reproducible order.

    This function does not implement detection logic itself. Instead, it coordinates the individual transformation
    steps and logs intermediate representations to make representation changes observable.
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
    Run the email pipeline and mirror all console output
    into data/output/email_pipeline/pipeline_output.txt
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