#!/usr/bin/env python3

"""
Reads the serialized RFC 5322 message as raw bytes.

This stage provides the byte-exact input representation before MIME parsing,
content-transfer decoding, or character decoding. Selected byte and hexadecimal
representations are printed for inspection.
"""

from src.utils.console import print_section


def step1_read_raw_input(EML_PATH):
    """
    Read the input email as raw bytes and print selected representations.

    Returns:
        bytes: The unmodified serialized email message.
    """

    f = open(EML_PATH, "rb")
    raw_bytes = f.read()
    f.close()

    print_section("RAW BYTES (python representation)")
    print(repr(raw_bytes))

    print_section("RAW BYTES (hex dump)")
    hex_list = []
    for b in raw_bytes:
        hex_list.append(hex(b))
    print(hex_list)

    # Use body context to avoid matching the same token in a header field.
    needle = b"on your Pay"
    idx = raw_bytes.find(needle)

    if idx == -1:
        print("\nBody keyword sequence b'on your Pay' not found.")
        return raw_bytes

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
