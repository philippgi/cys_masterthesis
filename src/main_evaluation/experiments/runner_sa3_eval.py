#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.main_evaluation.main_evaluation_utils.config_switcher import activate_spamassassin_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.utils.console import print_step, print_section


def run_sa3_eval():
    # Activate SpamAssassin SA3 config
    activate_spamassassin_config("sa3.cf")

    # Restart spamd so that the config is active and the existing Bayes DB is loaded
    restart_spamassassin()

    # Set directories
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/SA3"
    strict_output = output_root / "strict"
    extended_output = output_root / "extended"

    print_step("SA3 Evaluation")

    # ----------------------------------
    # Build trigger vocabulary from existing train set
    # ----------------------------------
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

    print_section("SA3 STRICT")

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
        experiment_id="SA3_strict",
        results_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=strict_output,
        filter_name="SpamAssassin",
        mechanism="rules_plus_bayes",
        rule_scope="extended_local_content",
        salting_condition="strict",
    )

    # ==================================
    # EXTENDED experiment
    # ==================================

    print_section("SA3 EXTENDED")

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
        experiment_id="SA3_extended",
        results_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=extended_output,
        filter_name="SpamAssassin",
        mechanism="rules_plus_bayes",
        rule_scope="extended_local_content",
        salting_condition="extended",
    )


if __name__ == "__main__":
    run_sa3_eval()