#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_evaluation
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section


def run_rs2_eval():
    activate_rspamd_config("rs2")
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/RS2"
    strict_output = output_root / "strict"
    extended_output = output_root / "extended"

    print_step("RS2 Evaluation")

    run_trigger_vocabulary(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )

    run_trigger_vocabulary(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )

    print_section("RS2 STRICT")

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
        experiment_id="RS2_strict",
        results_csv=strict_output / "rspamd_evaluation" / "rspamd_results.csv",
        paired_csv=strict_output / "rspamd_evaluation" / "rspamd_results_paired.csv",
        output_dir=strict_output,
        filter_name="Rspamd",
        mechanism="rules_plus_bayes",
        rule_scope="extended_local_content",
        salting_condition="strict",
    )

    print_section("RS2 EXTENDED")

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
        experiment_id="RS2_extended",
        results_csv=extended_output / "rspamd_evaluation" / "rspamd_results.csv",
        paired_csv=extended_output / "rspamd_evaluation" / "rspamd_results_paired.csv",
        output_dir=extended_output,
        filter_name="Rspamd",
        mechanism="rules_plus_bayes",
        rule_scope="extended_local_content",
        salting_condition="extended",
    )


if __name__ == "__main__":
    run_rs2_eval()