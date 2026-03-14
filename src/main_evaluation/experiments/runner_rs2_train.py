#!/usr/bin/env python3

from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.rspamd_training.runner import run_rspamd_training
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step


def run_rs2_train():
    activate_rspamd_config("rs2")
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    output_root = BASE_DIR / "data/output/RS2"

    print_step("RS2 Training")

    reset_pipeline_output()
    run_dataset_split(train_ratio=0.8)

    run_rspamd_training(
        output_root=output_root,
        dataset_split_dir=dataset_dir,
    )

    restart_rspamd()


if __name__ == "__main__":
    run_rs2_train()