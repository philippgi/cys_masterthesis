#!/usr/bin/env python3
from __future__ import annotations

from config import DATASET_SPLIT
from src.main_evaluation.rspamd_training.bayes_runner import run_rspamd_bayes_training
from src.utils.console import print_step, print_end


def run_rspamd_pilot_bayes_train() -> None:
    print_step("Rspamd Pilot - Bayes Train")
    run_rspamd_bayes_training(dataset_split_dir=DATASET_SPLIT)
    print_end("Rspamd Pilot - Bayes Train")


if __name__ == "__main__":
    run_rspamd_pilot_bayes_train()