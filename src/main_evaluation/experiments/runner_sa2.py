#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.main_evaluation_utils.config_switcher import activate_spamassassin_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.utils.console import print_step, print_section



def run_sa2():
    # Activate SpamAssassin SA2 config
    activate_spamassassin_config("sa2.cf")

    # Restart spamd
    restart_spamassassin()

    # Set directories
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/SA2"
    strict_output = output_root / "strict"
    extended_output = output_root / "extended"

    print_step("SA2 Experiment")

    # ----------------------------------
    # Reset pipeline outputs
    # ----------------------------------
    reset_pipeline_output()

    # ----------------------------------
    # Build trigger vocabulary (train set)
    # ----------------------------------
    run_dataset_split(train_ratio=0.8)

    run_trigger_vocabulary(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )

    run_trigger_vocabulary(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )

    # ==================================
    # STRICT experiment
    # ==================================

    print_section("SA2 STRICT")

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

    run_spamassassin_evaluation(
        output_root=strict_output,
        dataset_split_dir=dataset_dir,
    )

    build_experiment_summary(
        experiment_id="SA2_strict",
        results_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=strict_output,
        filter_name="SpamAssassin",
        mechanism="rules_only",
        rule_scope="extended_local_content",
        salting_condition="strict",
    )

    # ==================================
    # EXTENDED experiment
    # ==================================

    print_section("SA2 EXTENDED")

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

    run_spamassassin_evaluation(
        output_root=extended_output,
        dataset_split_dir=dataset_dir,
    )

    build_experiment_summary(
        experiment_id="SA2_extended",
        results_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=extended_output,
        filter_name="SpamAssassin",
        mechanism="rules_only",
        rule_scope="extended_local_content",
        salting_condition="extended",
    )


if __name__ == "__main__":
    run_sa2()
