#!/usr/bin/env python3
"""
RS3 evaluation runner.

This module orchestrates the complete RS3 experiment for Rspamd
(rules + Neural) on the test split.

Workflow:
1. Activate the dedicated Rspamd configuration for RS3
2. Recreate the Rspamd stack so that the active config is loaded
3. Build trigger vocabularies for strict, extended, and broad salting
4. Run trigger coverage
5. Generate salted email variants
6. Evaluate baseline spam, baseline ham, and salted spam with Rspamd
7. Build the experiment summary for all salting conditions

The evaluation itself is implemented in:
    src/main_evaluation/rspamd_evaluation/neural_runner_rs3.py
"""

from config import BASE_DIR

from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_evaluation
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section


def run_rs3_eval():
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/RS3"

    strict_output = output_root / "strict"
    extended_output = output_root / "extended"
    broad_output = output_root / "broad"

    experiments = [
        {
            "name": "STRICT",
            "output_root": strict_output,
            "experiment_id": "RS3_strict",
            "salting_vocabulary": "strict",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
        },
        {
            "name": "EXTENDED",
            "output_root": extended_output,
            "experiment_id": "RS3_extended",
            "salting_vocabulary": "extended",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
        },
        {
            "name": "BROAD",
            "output_root": broad_output,
            "experiment_id": "RS3_broad",
            "salting_vocabulary": "broad",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
        },
    ]

    print_step("RS3 Evaluation")
    activate_rspamd_config("rs3")
    restart_rspamd()

    run_trigger_vocabulary(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )
    run_trigger_vocabulary(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )
    run_trigger_vocabulary(
        output_root=broad_output,
        dataset_split_dir=dataset_dir,
    )

    for exp in experiments:
        print_section(f"RS3 {exp['name']}")

        run_trigger_coverage(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
            salting_vocabulary=exp["salting_vocabulary"],
        )

        run_salted_email_generator(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
            salting_vocabulary=exp["salting_vocabulary"],
            subject_max_insertions=exp["subject_max_insertions"],
            body_max_insertions=exp["body_max_insertions"],
            salt_mode=exp["salt_mode"],
            insert_after_index=exp["insert_after_index"],
            fragment_max_positions=exp["fragment_max_positions"],
        )

        run_rspamd_evaluation(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
        )

        build_experiment_summary(
            experiment_id=exp["experiment_id"],
            results_csv=exp["output_root"] / "rspamd_evaluation" / "rspamd_results.csv",
            paired_csv=exp["output_root"] / "rspamd_evaluation" / "rspamd_results_paired.csv",
            output_dir=exp["output_root"],
            filter_name="Rspamd",
            mechanism="rules_plus_neural",
            rule_scope="extended_local_content",
            salting_condition=exp["salting_vocabulary"],
            salting_config={
                "subject_max_insertions": exp["subject_max_insertions"],
                "body_max_insertions": exp["body_max_insertions"],
                "salt_mode": exp["salt_mode"],
                "insert_after_index": exp["insert_after_index"],
                "fragment_max_positions": exp["fragment_max_positions"],
            },
        )


if __name__ == "__main__":
    run_rs3_eval()