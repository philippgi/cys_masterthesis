#!/usr/bin/env python3
"""
This module orchestrates the salted email generation step.
"""

from config import (
    SALT_CODEPOINTS,
    SALT_SUBJECT_MAX_INSERTIONS,
    SALT_BODY_MAX_INSERTIONS,
    SALT_INSERT_AFTER_INDEX,
    SALTING_VOCABULARY,
    OUTPUT_ROOT,
    DATASET_SPLIT,
)

from src.utils.console import print_step, print_section, print_kv, print_end

from src.main_evaluation.salted_email_generator.generator import (
    read_candidate_rows,
    load_trigger_words,
    parse_email,
    apply_salting_to_message,
    build_variant_filename,
    write_email,
    write_salting_log,
)


def run_salted_email_generator(
    output_root=None,
    dataset_split_dir=None,
    salting_vocabulary=None,
):

    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir
    salting_vocabulary = SALTING_VOCABULARY if salting_vocabulary is None else salting_vocabulary

    salted_email_output_dir = output_root / "salted_email_generator"
    salted_emails_dir = salted_email_output_dir / "emails"
    salting_log_csv = salted_email_output_dir / "salting_log.csv"

    salted_candidates_csv = (
        output_root / "salting_candidate_selection" / "salted_candidates.csv"
    )

    strict_trigger_words_path = (
        output_root / "trigger_vocabulary" / "trigger_words_strict.json"
    )
    extended_trigger_words_path = (
        output_root / "trigger_vocabulary" / "trigger_words_extended.json"
    )

    test_spam_dir = dataset_split_dir / "test" / "spam"

    salted_email_output_dir.mkdir(parents=True, exist_ok=True)
    salted_emails_dir.mkdir(parents=True, exist_ok=True)

    print_step("Salted Email Generation")

    candidate_rows = read_candidate_rows(salted_candidates_csv)

    strict_triggers = load_trigger_words(strict_trigger_words_path)
    extended_triggers = load_trigger_words(extended_trigger_words_path)

    if salting_vocabulary == "strict":
        vocabularies = {"strict": strict_triggers}
    elif salting_vocabulary == "extended":
        vocabularies = {"extended": extended_triggers}
    else:
        raise ValueError(
            f"Invalid SALTING_VOCABULARY '{salting_vocabulary}'. "
            f"Expected 'strict' or 'extended'."
        )

    salting_log_rows = []
    total_variants = 0

    for row in candidate_rows:
        message_id = row["message_id"]
        email_path = test_spam_dir / message_id

        if not email_path.is_file():
            print_section(f"WARNING: source email not found: {message_id}")
            continue

        original_msg, mbox_from_line = parse_email(email_path)

        for vocab_type, trigger_words in vocabularies.items():
            for codepoint_name, codepoint_char in SALT_CODEPOINTS.items():

                salted_msg, subject_targets, body_targets, n_insert_subject, n_insert_body, body_part_found = apply_salting_to_message(
                    original_msg=original_msg,
                    trigger_words=trigger_words,
                    codepoint=codepoint_char,
                    subject_max_insertions=SALT_SUBJECT_MAX_INSERTIONS,
                    body_max_insertions=SALT_BODY_MAX_INSERTIONS,
                    insert_after_index=SALT_INSERT_AFTER_INDEX,
                )

                if (n_insert_subject + n_insert_body) == 0:
                    continue

                variant_filename = build_variant_filename(
                    original_filename=message_id,
                    vocab_type=vocab_type,
                    codepoint_name=codepoint_name,
                )

                output_path = salted_emails_dir / variant_filename
                write_email(salted_msg, output_path, mbox_from_line=mbox_from_line)

                salting_log_rows.append(
                    {
                        "message_id": message_id,
                        "variant_filename": variant_filename,
                        "vocab_type": vocab_type,
                        "codepoint": codepoint_name,
                        "n_insert_subject": n_insert_subject,
                        "n_insert_body": n_insert_body,
                        "body_part_found": body_part_found,
                        "subject_targets": subject_targets,
                        "body_targets": body_targets,
                    }
                )

                total_variants += 1

    write_salting_log(
        salting_log_rows,
        technical_csv=salting_log_csv,
        readable_csv=salted_email_output_dir / "salting_log_readable.csv",
    )

    print_section("Generation summary")
    print_kv("Candidate emails processed", len(candidate_rows))
    print_kv("Salted variants generated", total_variants)
    print_kv("Output directory", salted_email_output_dir)

    print_end("Salted Email Generation")
