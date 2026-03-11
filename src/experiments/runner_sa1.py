#!/usr/bin/env python3

from config import BASE_DIR

from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.trigger_coverage.runner import run_trigger_coverage
from src.salted_email_generator.runner import run_salted_email_generator
from src.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.utils.reset_output import reset_pipeline_output
from src.utils.config_switcher import activate_spamassassin_config
from src.utils.container_control import restart_spamassassin
from src.analysis.build_experiment_summary import build_experiment_summary


def run_sa1():
    # Activate SpamAssassin SA1 config
    activate_spamassassin_config("sa1.cf")

    # Restart spamd
    restart_spamassassin()

    # Set Directories
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/SA1"
    strict_output = output_root / "strict"
    extended_output = output_root / "extended"

    print("===== SA1 Experiment =====")

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

    print("\n--- SA1 STRICT ---")

    run_dataset_split(train_ratio=0.0)

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
        experiment_id="SA1_strict",
        results_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=strict_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=strict_output,
        filter_name="SpamAssassin",
        mechanism="rules_only",
        rule_scope="strict_lexical",
        salting_condition="strict",
    )

    # ==================================
    # EXTENDED experiment
    # ==================================

    print("\n--- SA1 EXTENDED ---")

    run_dataset_split(train_ratio=0.0)

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
        experiment_id="SA1_extended",
        results_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results.csv",
        paired_csv=extended_output / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
        output_dir=extended_output,
        filter_name="SpamAssassin",
        mechanism="rules_only",
        rule_scope="strict_lexical",
        salting_condition="extended",
    )


if __name__ == "__main__":
    run_sa1()