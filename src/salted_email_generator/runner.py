#!/usr/bin/env python3
"""
This module orchestrates the salted email generation step.

It reads the selected spam candidates, loads the strict and extended trigger
vocabularies, generates salted .eml variants, and writes an aggregated
salting log for later evaluation.
"""

from config import (
    SALTED_CANDIDATES_CSV,
    SALTED_EMAIL_OUTPUT_DIR,
    SALTED_EMAILS_DIR,
    SALTING_LOG_CSV,
    STRICT_TRIGGER_WORDS_PATH,
    EXTENDED_TRIGGER_WORDS_PATH,
    TEST_SPAM_DIR,
    SALT_CODEPOINTS,
    SALT_SUBJECT_MAX_INSERTIONS,
    SALT_BODY_MAX_INSERTIONS,
    SALT_INSERT_AFTER_INDEX,
    SALTING_VOCABULARY,
)

from src.salted_email_generator.generator import (
    read_candidate_rows,
    load_trigger_words,
    parse_email,
    apply_salting_to_message,
    build_variant_filename,
    write_email,
    write_salting_log,
)


def run_salted_email_generator():
    """
    Runs the salted email generation step.

    Workflow:
    1. Load the selected spam candidates.
    2. Load strict and extended trigger vocabularies.
    3. Parse each original spam email.
    4. Generate salted variants for all vocabulary/codepoint combinations.
    5. Write one .eml file per generated variant.
    6. Write an aggregated salting log.
    """
    SALTED_EMAIL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SALTED_EMAILS_DIR.mkdir(parents=True, exist_ok=True)

    candidate_rows = read_candidate_rows(SALTED_CANDIDATES_CSV)

    strict_triggers = load_trigger_words(STRICT_TRIGGER_WORDS_PATH)
    extended_triggers = load_trigger_words(EXTENDED_TRIGGER_WORDS_PATH)

    if SALTING_VOCABULARY == "strict":
        vocabularies = {
            "strict": strict_triggers,
        }
    elif SALTING_VOCABULARY == "extended":
        vocabularies = {
            "extended": extended_triggers,
        }
    else:
        raise ValueError(
            f"Invalid SALTING_VOCABULARY '{SALTING_VOCABULARY}'. "
            f"Expected 'strict' or 'extended'."
        )

    salting_log_rows = []
    total_variants = 0

    for row in candidate_rows:
        message_id = row["message_id"]
        email_path = TEST_SPAM_DIR / message_id

        if not email_path.is_file():
            print(f"WARNING: source email not found: {message_id}")
            continue

        original_msg = parse_email(email_path)

        for vocab_type, trigger_words in vocabularies.items():
            for codepoint_name, codepoint_char in SALT_CODEPOINTS.items():

                salted_msg, subject_targets, body_targets, n_insert_subject, n_insert_body = apply_salting_to_message(
                    original_msg=original_msg,
                    trigger_words=trigger_words,
                    codepoint=codepoint_char,
                    subject_max_insertions=SALT_SUBJECT_MAX_INSERTIONS,
                    body_max_insertions=SALT_BODY_MAX_INSERTIONS,
                    insert_after_index=SALT_INSERT_AFTER_INDEX,
                )

                # Skip variants with no actual modification.
                if (n_insert_subject + n_insert_body) == 0:
                    continue

                variant_filename = build_variant_filename(
                    original_filename=message_id,
                    vocab_type=vocab_type,
                    codepoint_name=codepoint_name,
                )

                output_path = SALTED_EMAILS_DIR / variant_filename
                write_email(salted_msg, output_path)

                salting_log_rows.append(
                    {
                        "message_id": message_id,
                        "variant_filename": variant_filename,
                        "vocab_type": vocab_type,
                        "codepoint": codepoint_name,
                        "n_insert_subject": n_insert_subject,
                        "n_insert_body": n_insert_body,
                        "subject_targets": subject_targets,
                        "body_targets": body_targets,
                    }
                )

                total_variants += 1

    write_salting_log(
        salting_log_rows,
        technical_csv=SALTING_LOG_CSV,
        readable_csv=SALTED_EMAIL_OUTPUT_DIR / "salting_log_readable.csv",
    )

    print("Salted Email Generator:")
    print(f"Candidate emails processed: {len(candidate_rows)}")
    print(f"Salted variants generated: {total_variants}")
    print(f"Output directory: {SALTED_EMAIL_OUTPUT_DIR}")