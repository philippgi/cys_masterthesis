#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from config import (
    BASE_DIR,
    PILOT_SALT_FRAGMENT_MAX_POSITIONS,
    PILOT_SALT_INSERT_AFTER_INDEX,
    PILOT_SALT_MODE,
)
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_scan
from src.pilot.rspamd.bayes_based.cases import BAYES_CASES, CODEPOINT_CHAR, CODEPOINT_NAME
from src.pilot.rspamd.rule_based.template_builder import create_paired_bytes, write_message
from src.utils.console import print_step, print_section, print_kv, print_end


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/rspamd/bayes"
TEST_UNSALTED_DIR = OUTPUT_ROOT / "messages" / "unsalted"
TEST_SALTED_DIR = OUTPUT_ROOT / "messages" / "salted"
DISCOVERY_DIR = OUTPUT_ROOT / "discovery"
RESULTS_DIR = OUTPUT_ROOT / "results"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text or "")


def _unique_candidate_tokens(case) -> tuple[list[str], list[str]]:
    subject_tokens = [t for t in _tokenize_text(case.subject) if len(t) >= 4]
    body_tokens = [t for t in _tokenize_text(case.body) if len(t) >= 4]
    return list(dict.fromkeys(subject_tokens)), list(dict.fromkeys(body_tokens))


def _build_salted_variant(
    case,
    target_tokens_subject: tuple[str, ...],
    target_tokens_body: tuple[str, ...],
    suffix: str,
) -> tuple[Path, dict]:
    _, salted_bytes, counts = create_paired_bytes(
        subject=case.subject,
        body=case.body,
        target_tokens_subject=target_tokens_subject,
        target_tokens_body=target_tokens_body,
        codepoint=CODEPOINT_CHAR,
        from_addr="pilot@example.test",
        to_addr="victim@example.test",
    )

    salted_path = TEST_SALTED_DIR / f"{case.case_id}_{suffix}.eml"
    write_message(salted_path, salted_bytes)
    return salted_path, counts


def _scan_summary(email_path: Path) -> dict:
    scan = run_rspamd_scan(email_path)
    return {
        "spam_flag": scan["spam_flag"],
        "score": scan["score"],
        "threshold": scan["threshold"],
        "action": scan["action"],
        "rules": scan["rules"],
        "has_bayes": scan["has_bayes"],
        "bayes_symbol": scan["bayes_symbol"],
        "bayes_score": scan["bayes_score"],
        "raw_output": scan["raw_output"],
    }


def _delta(a, b):
    if a is None or b is None:
        return None
    return b - a


def run_rspamd_pilot_bayes_eval() -> None:
    print_step("Rspamd Pilot - Bayes Eval")

    case = BAYES_CASES[0]
    unsalted_path = TEST_UNSALTED_DIR / f"{case.case_id}_unsalted.eml"

    if not unsalted_path.exists():
        raise FileNotFoundError(
            f"Unsalted pilot mail not found: {unsalted_path}. "
            f"Run run_rspamd_pilot_bayes_prepare() first."
        )

    print_section("Pilot case")
    print_kv("case_id", case.case_id)
    print_kv("title", case.title)

    print_section("Baseline scan")
    baseline = _scan_summary(unsalted_path)
    print_kv("score", baseline["score"])
    print_kv("action", baseline["action"])
    print_kv("has_bayes", baseline["has_bayes"])
    print_kv("bayes_symbol", baseline["bayes_symbol"])
    print_kv("bayes_score", baseline["bayes_score"])

    if not baseline["has_bayes"]:
        raise RuntimeError(
            "Pilot mail does not trigger any BAYES_* symbol. "
            "Train Bayes first or choose a different spam mail."
        )

    subject_candidates, body_candidates = _unique_candidate_tokens(case)

    print_section("Discovery candidates")
    print_kv("subject_candidates", subject_candidates)
    print_kv("body_candidates", body_candidates)

    discovery_rows: list[dict] = []

    for token in subject_candidates:
        salted_path, counts = _build_salted_variant(
            case=case,
            target_tokens_subject=(token,),
            target_tokens_body=(),
            suffix=f"discovery_subject_{token}",
        )
        salted = _scan_summary(salted_path)

        discovery_rows.append(
            {
                "case_id": case.case_id,
                "surface": "subject",
                "token": token,
                "n_insert_subject": counts["n_insert_subject"],
                "n_insert_body": counts["n_insert_body"],
                "unsalted_score": baseline["score"],
                "salted_score": salted["score"],
                "delta_score": _delta(baseline["score"], salted["score"]),
                "unsalted_bayes_symbol": baseline["bayes_symbol"],
                "salted_bayes_symbol": salted["bayes_symbol"],
                "unsalted_bayes_score": baseline["bayes_score"],
                "salted_bayes_score": salted["bayes_score"],
                "delta_bayes_score": _delta(baseline["bayes_score"], salted["bayes_score"]),
                "salted_has_bayes": salted["has_bayes"],
                "salted_action": salted["action"],
                "salted_spam_flag": salted["spam_flag"],
            }
        )

    for token in body_candidates:
        salted_path, counts = _build_salted_variant(
            case=case,
            target_tokens_subject=(),
            target_tokens_body=(token,),
            suffix=f"discovery_body_{token}",
        )
        salted = _scan_summary(salted_path)

        discovery_rows.append(
            {
                "case_id": case.case_id,
                "surface": "body",
                "token": token,
                "n_insert_subject": counts["n_insert_subject"],
                "n_insert_body": counts["n_insert_body"],
                "unsalted_score": baseline["score"],
                "salted_score": salted["score"],
                "delta_score": _delta(baseline["score"], salted["score"]),
                "unsalted_bayes_symbol": baseline["bayes_symbol"],
                "salted_bayes_symbol": salted["bayes_symbol"],
                "unsalted_bayes_score": baseline["bayes_score"],
                "salted_bayes_score": salted["bayes_score"],
                "delta_bayes_score": _delta(baseline["bayes_score"], salted["bayes_score"]),
                "salted_has_bayes": salted["has_bayes"],
                "salted_action": salted["action"],
                "salted_spam_flag": salted["spam_flag"],
            }
        )

    discovery_rows = sorted(
        discovery_rows,
        key=lambda row: (
            row["delta_bayes_score"] is None,
            row["delta_bayes_score"] if row["delta_bayes_score"] is not None else 9999,
            row["delta_score"] if row["delta_score"] is not None else 9999,
        )
    )

    discovery_csv = DISCOVERY_DIR / f"{case.case_id}_bayes_token_impact.csv"
    discovery_json = DISCOVERY_DIR / f"{case.case_id}_bayes_token_impact_summary.json"
    _write_csv(discovery_csv, discovery_rows)

    top_rows = [row for row in discovery_rows if row["delta_bayes_score"] is not None][:5]

    target_tokens_subject = tuple(row["token"] for row in top_rows if row["surface"] == "subject")
    target_tokens_body = tuple(row["token"] for row in top_rows if row["surface"] == "body")

    discovery_summary = {
        "case_id": case.case_id,
        "title": case.title,
        "baseline": baseline,
        "salt_mode": PILOT_SALT_MODE,
        "insert_after_index": PILOT_SALT_INSERT_AFTER_INDEX,
        "fragment_max_positions": PILOT_SALT_FRAGMENT_MAX_POSITIONS,
        "top_rows": top_rows,
        "selected_tokens_subject": list(target_tokens_subject),
        "selected_tokens_body": list(target_tokens_body),
    }
    _write_json(discovery_json, discovery_summary)

    print_section("Discovery summary")
    print_kv("discovery_csv", discovery_csv)
    print_kv("selected_tokens_subject", list(target_tokens_subject))
    print_kv("selected_tokens_body", list(target_tokens_body))

    print_section("Final eval")
    final_salted_path, final_counts = _build_salted_variant(
        case=case,
        target_tokens_subject=target_tokens_subject,
        target_tokens_body=target_tokens_body,
        suffix="salted_final",
    )
    final_salted = _scan_summary(final_salted_path)

    results_csv = RESULTS_DIR / "rspamd_pilot_bayes_results.csv"
    results_json = RESULTS_DIR / "rspamd_pilot_bayes_summary.json"
    manifest_json = RESULTS_DIR / f"{case.case_id}_salting_manifest.json"

    rows = [
        {
            "case_id": case.case_id,
            "variant": "unsalted",
            "score": baseline["score"],
            "threshold": baseline["threshold"],
            "action": baseline["action"],
            "spam_flag": baseline["spam_flag"],
            "has_bayes": baseline["has_bayes"],
            "bayes_symbol": baseline["bayes_symbol"],
            "bayes_score": baseline["bayes_score"],
            "n_insert_subject": 0,
            "n_insert_body": 0,
            "target_tokens_subject": "",
            "target_tokens_body": "",
            "message_path": str(unsalted_path),
        },
        {
            "case_id": case.case_id,
            "variant": "salted",
            "score": final_salted["score"],
            "threshold": final_salted["threshold"],
            "action": final_salted["action"],
            "spam_flag": final_salted["spam_flag"],
            "has_bayes": final_salted["has_bayes"],
            "bayes_symbol": final_salted["bayes_symbol"],
            "bayes_score": final_salted["bayes_score"],
            "n_insert_subject": final_counts["n_insert_subject"],
            "n_insert_body": final_counts["n_insert_body"],
            "target_tokens_subject": "|".join(target_tokens_subject),
            "target_tokens_body": "|".join(target_tokens_body),
            "message_path": str(final_salted_path),
        },
    ]
    _write_csv(results_csv, rows)

    summary = {
        "case_id": case.case_id,
        "title": case.title,
        "salt_mode": PILOT_SALT_MODE,
        "insert_after_index": PILOT_SALT_INSERT_AFTER_INDEX,
        "fragment_max_positions": PILOT_SALT_FRAGMENT_MAX_POSITIONS,
        "selected_tokens_subject": list(target_tokens_subject),
        "selected_tokens_body": list(target_tokens_body),
        "unsalted_score": baseline["score"],
        "salted_score": final_salted["score"],
        "delta_score": _delta(baseline["score"], final_salted["score"]),
        "unsalted_bayes_symbol": baseline["bayes_symbol"],
        "salted_bayes_symbol": final_salted["bayes_symbol"],
        "unsalted_bayes_score": baseline["bayes_score"],
        "salted_bayes_score": final_salted["bayes_score"],
        "delta_bayes_score": _delta(baseline["bayes_score"], final_salted["bayes_score"]),
        "unsalted_action": baseline["action"],
        "salted_action": final_salted["action"],
        "unsalted_spam_flag": baseline["spam_flag"],
        "salted_spam_flag": final_salted["spam_flag"],
    }
    _write_json(results_json, summary)

    manifest = {
        "case_id": case.case_id,
        "codepoint": CODEPOINT_NAME,
        "target_tokens_subject": list(target_tokens_subject),
        "target_tokens_body": list(target_tokens_body),
        "salt_mode": PILOT_SALT_MODE,
        "insert_after_index": PILOT_SALT_INSERT_AFTER_INDEX,
        "fragment_max_positions": PILOT_SALT_FRAGMENT_MAX_POSITIONS,
        "n_insert_subject": final_counts["n_insert_subject"],
        "n_insert_body": final_counts["n_insert_body"],
    }
    _write_json(manifest_json, manifest)

    print_section("Unsalted")
    print_kv("score", baseline["score"])
    print_kv("action", baseline["action"])
    print_kv("bayes_symbol", baseline["bayes_symbol"])
    print_kv("bayes_score", baseline["bayes_score"])

    print_section("Salted")
    print_kv("score", final_salted["score"])
    print_kv("action", final_salted["action"])
    print_kv("bayes_symbol", final_salted["bayes_symbol"])
    print_kv("bayes_score", final_salted["bayes_score"])

    print_section("Salting")
    print_kv("target_tokens_subject", list(target_tokens_subject))
    print_kv("target_tokens_body", list(target_tokens_body))
    print_kv("n_insert_subject", final_counts["n_insert_subject"])
    print_kv("n_insert_body", final_counts["n_insert_body"])

    print_section("Output files")
    print_kv("discovery_csv", discovery_csv)
    print_kv("discovery_json", discovery_json)
    print_kv("results_csv", results_csv)
    print_kv("results_json", results_json)
    print_kv("manifest_json", manifest_json)

    print_end("Rspamd Pilot - Bayes Eval")


if __name__ == "__main__":
    run_rspamd_pilot_bayes_eval()