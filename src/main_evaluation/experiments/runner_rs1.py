#!/usr/bin/env python3

from config import BASE_DIR
from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_evaluation
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.reset_output import reset_pipeline_output
from src.utils.console import print_step, print_section


def run_rs1():
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/experiments/RS1"

    strict_output = output_root / "strict"
    extended_output = output_root / "extended"
    broad_output = output_root / "broad"

    experiments = [
        {
            "name": "STRICT",
            "output_root": strict_output,
            "experiment_id": "RS1_strict",
            "salting_vocabulary": "strict",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
            "rule_scope": "strict_lexical",
        },
        {
            "name": "EXTENDED",
            "output_root": extended_output,
            "experiment_id": "RS1_extended",
            "salting_vocabulary": "extended",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
            "rule_scope": "strict_lexical",
        },
        {
            "name": "BROAD",
            "output_root": broad_output,
            "experiment_id": "RS1_broad",
            "salting_vocabulary": "broad",
            "subject_max_insertions": 1,
            "body_max_insertions": 3,
            "salt_mode": "single",
            "insert_after_index": 2,
            "fragment_max_positions": None,
            "rule_scope": "strict_lexical",
        },
    ]

    print_step("RS1 Experiment")

    activate_rspamd_config("rs1")
    restart_rspamd()

    run_dataset_split(train_ratio=0.8)

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
        print_section(f"RS1 {exp['name']}")

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
            mechanism="rules_only",
            rule_scope=exp["rule_scope"],
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
    run_rs1()
