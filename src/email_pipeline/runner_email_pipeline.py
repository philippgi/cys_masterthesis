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
from src.email_pipeline.step1_raw import step1_read_raw_input
from src.email_pipeline.step2_mime import step2_parse_mime
from src.email_pipeline.step3_transfer import step3_transfer_decode_part
from src.email_pipeline.step4_charset import step4_charset_decode
from src.email_pipeline.step5_normalization import step5_normalize
from src.email_pipeline.step6_segmentation import step6_word_segmentation
from config import EML_PATH


def run_email_pipeline():
    """
    Execute the complete message representation pipeline in a linear, reproducible order.

    This function does not implement detection logic itself. Instead, it coordinates the individual transformation
    steps and logs intermediate representations to make representation changes observable.
    """

    print("=== STEP 1: RAW INPUT ===")
    raw_bytes = step1_read_raw_input(EML_PATH)

    print("\n=== STEP 2: MIME PARSING + PART SELECTION ===")
    msg, text_part = step2_parse_mime(raw_bytes)

    print("\n=== STEP 3: CONTENT-TRANSFER DECODING (selected part) ===")
    decoded_bytes = step3_transfer_decode_part(text_part)

    print("\n=== STEP 4: CHARSET DECODING (declared charset) ===")
    unicode_text = step4_charset_decode(text_part, decoded_bytes)

    print("\n=== STEP 5: UNICODE NORMALIZATION ===")
    normalized_text = step5_normalize(unicode_text, apply_form="NFC")

    print("\n=== STEP 6: TOKENIZATION ===")
    _ = step6_word_segmentation(normalized_text)


if __name__ == "__main__":
    run_email_pipeline()
