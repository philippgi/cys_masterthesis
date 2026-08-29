#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.utils.console import print_step, print_section


def run_sa3_train():
    activate_spamassassin_config("sa3.cf")
    restart_spamassassin()

    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/experiments/SA3"

    print_step("SA3 Training")

    run_dataset_split(train_ratio=0.8)

    run_spamassassin_training(
        output_root=output_root,
        dataset_split_dir=dataset_dir,
    )

    restart_spamassassin()


if __name__ == "__main__":
    run_sa3_train()