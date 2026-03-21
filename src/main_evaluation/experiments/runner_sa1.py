#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.main_evaluation.analysis.build_experiment_summary import build_experiment_summary
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.utils.reset_output import reset_pipeline_output
from src.utils.console import print_step, print_section


def run_sa1():
    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/SA1"

    strict_output = output_root / "strict"
    extended_output = output_root / "extended"
    broad_output = output_root / "broad"

    experiments = [
        {
            "name": "STRICT",
            "output_root": strict_output,
            "experiment_id": "SA1_strict",
            "salting_vocabulary": "strict",
            "rule_scope": "strict_lexical",
        },
        {
            "name": "EXTENDED",
            "output_root": extended_output,
            "experiment_id": "SA1_extended",
            "salting_vocabulary": "extended",
            "rule_scope": "strict_lexical",
        },
        {
            "name": "BROAD",
            "output_root": broad_output,
            "experiment_id": "SA1_broad",
            "salting_vocabulary": "broad",
            "rule_scope": "strict_lexical",
        },
    ]

    print_step("SA1 Experiment")

    activate_spamassassin_config("sa1.cf")
    restart_spamassassin()

    reset_pipeline_output()
    run_dataset_split(train_ratio=1.0)

    run_trigger_vocabulary(output_root=strict_output, dataset_split_dir=dataset_dir)
    run_trigger_vocabulary(output_root=extended_output, dataset_split_dir=dataset_dir)
    run_trigger_vocabulary(output_root=broad_output, dataset_split_dir=dataset_dir)

    for exp in experiments:
        print_section(f"SA1 {exp['name']}")

        run_trigger_coverage(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
            salting_vocabulary=exp["salting_vocabulary"],
        )

        run_salted_email_generator(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
            salting_vocabulary=exp["salting_vocabulary"],
        )

        run_spamassassin_evaluation(
            output_root=exp["output_root"],
            dataset_split_dir=dataset_dir,
        )

        build_experiment_summary(
            experiment_id=exp["experiment_id"],
            results_csv=exp["output_root"] / "spamassassin_evaluation" / "spamassassin_results.csv",
            paired_csv=exp["output_root"] / "spamassassin_evaluation" / "spamassassin_results_paired.csv",
            output_dir=exp["output_root"],
            filter_name="SpamAssassin",
            mechanism="rules_only",
            rule_scope=exp["rule_scope"],
            salting_condition=exp["salting_vocabulary"],
        )


if __name__ == "__main__":
    run_sa1()
