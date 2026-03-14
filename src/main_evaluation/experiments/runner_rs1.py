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
from src.utils.console import print_step, print_section, print_end


def run_rs1():
    print_step("RS1 Experiment")

    activate_rspamd_config("rs1")
    restart_rspamd()

    reset_pipeline_output()

    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/RS1"

    strict_output = output_root / "strict"
    extended_output = output_root / "extended"

    run_dataset_split(train_ratio=0.8)

    run_trigger_vocabulary(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )

    run_trigger_vocabulary(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )

    print_section("\nRS1 STRICT")

    run_trigger_coverage(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="strict",
    )

    run_salted_email_generator(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="strict",
    )

    run_rspamd_evaluation(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )

    build_experiment_summary(
        experiment_id="RS1_strict",
        results_csv=strict_output / "rspamd_evaluation" / "rspamd_results.csv",
        paired_csv=strict_output / "rspamd_evaluation" / "rspamd_results_paired.csv",
        output_dir=strict_output,
        filter_name="Rspamd",
        mechanism="rules_only",
        rule_scope="strict_lexical",
        salting_condition="strict",
    )

    print_section("RS1 EXTENDED")

    run_trigger_coverage(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="extended",
    )

    run_salted_email_generator(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="extended",
    )

    run_rspamd_evaluation(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )

    build_experiment_summary(
        experiment_id="RS1_extended",
        results_csv=extended_output / "rspamd_evaluation" / "rspamd_results.csv",
        paired_csv=extended_output / "rspamd_evaluation" / "rspamd_results_paired.csv",
        output_dir=extended_output,
        filter_name="Rspamd",
        mechanism="rules_only",
        rule_scope="strict_lexical",
        salting_condition="extended",
    )

    print_end("RS1 Experiment")


if __name__ == "__main__":
    run_rs1()