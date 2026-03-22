#!/usr/bin/env python3

from src.main_evaluation.rspamd_training.neural_runner_rs4 import run_rspamd_neural_training_rs4
from src.utils.console import print_step


def run_rs4_train(train_salt_ratio: float = 0.5):
    print_step("RS4 Training")
    run_rspamd_neural_training_rs4(train_salt_ratio=train_salt_ratio)


if __name__ == "__main__":
    run_rs4_train()