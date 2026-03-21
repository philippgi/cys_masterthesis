from __future__ import annotations

CODEPOINT_CHAR = "\u200b"
CODEPOINT_NAME = "U+200B"


class SABayesCase:
    def __init__(self, case_id: str, title: str):
        self.case_id = case_id
        self.title = title


SAB001 = SABayesCase("SAB001", "Basic verification mail")
