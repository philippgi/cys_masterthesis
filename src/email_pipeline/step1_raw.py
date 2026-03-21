#!/usr/bin/env python3

"""
Step 1 - Raw Message Bytes
This function reads an RFC 5322 compliant email message as a raw
byte stream. No parsing, decoding, or interpretation is applied at this stage.

The goal of this step is to establish a byte-exact baseline of the message
content prior to any MIME parsing, content-transfer decoding, or character
set decoding. Multiple representations are printed to make the underlying
byte sequence observable without modification.

This step corresponds to the initial message representation on the receiver
side, before any processing by MIME parsers or content-based filters.
"""
from src.utils.console import print_section


def step1_read_raw_input(EML_PATH):
    """
    Reads the .eml file as raw bytes and prints different representations for inspection.
    Returns:
        raw_bytes (bytes): The unmodified byte stream of the email message.
    """

    # Read the message source as raw bytes
    f = open(EML_PATH, "rb")
    raw_bytes = f.read()
    f.close()

    # Python bytes representation (shows escape sequences explicitly)
    print_section("RAW BYTES (python representation)")
    print(repr(raw_bytes))

    # Hexadecimal representation (byte-exact view)
    print_section("RAW BYTES (hex dump)")
    hex_list = []
    for b in raw_bytes:
        hex_list.append(hex(b))
    print(hex_list)

    # This section is for identifying the zero-width Unicode injected keyword
    # Locate the keyword sequence in the message body to avoid matching headers (byte-literal)
    needle = b"on your Pay"
    idx = raw_bytes.find(needle)

    if idx == -1:
        print("\nBody keyword sequence b'on your Pay' not found.")
        return raw_bytes

    # Extract a small byte window around the keyword occurrence
    before = 20
    after = 60
    start = idx - before
    end = idx + after

    if start < 0:
        start = 0
    if end > len(raw_bytes):
        end = len(raw_bytes)

    window = raw_bytes[start:end]

    print_section("RAW BYTES (body keyword window)")
    print(window)

    print_section("HEX BYTES (body keyword window)")
    window_hex = []
    for b in window:
        window_hex.append(hex(b))
    print(window_hex)

    return raw_bytes
