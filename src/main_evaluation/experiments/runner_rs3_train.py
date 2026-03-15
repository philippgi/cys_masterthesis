#!/usr/bin/env python3

from src.main_evaluation.rspamd_training.runner import run_rspamd_training
from src.utils.console import print_step


def run_rs3_train():
    print_step("RS3 Training")
    run_rspamd_training()


if __name__ == "__main__":
    run_rs3_train()