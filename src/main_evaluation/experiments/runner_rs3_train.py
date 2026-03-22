#!/usr/bin/env python3

from src.main_evaluation.rspamd_training.neural_runner_rs3 import run_rspamd_neural_training
from src.utils.console import print_step


def run_rs3_train():
    print_step("RS3 Training")
    run_rspamd_neural_training()


if __name__ == "__main__":
    run_rs3_train()