#!/usr/bin/env python3

from src.main_evaluation.rspamd_training.runner_rs4 import run_rspamd_training_rs4
from src.utils.console import print_step


def run_rs4_train(ratio: float):
    run_rspamd_training_rs4(train_salt_ratio=ratio)


if __name__ == "__main__":
    run_rs4_train(0.25)