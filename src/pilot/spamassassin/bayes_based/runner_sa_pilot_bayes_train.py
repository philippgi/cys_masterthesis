"""
Trains the SpamAssassin Bayes classifier for the pilot study.

The pilot-specific configuration is activated before the shared SpamAssassin
training pipeline is executed on the configured training split.
"""

from __future__ import annotations

from config import (
    DATASET_SPLIT,
    PILOT_SA_BAYES_CONFIG_NAME,
    PILOT_SA_BAYES_TRAINING_OUTPUT_DIR,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.utils.console import print_end, print_step


def run_sa_pilot_bayes_train() -> None:
    """
    Run Bayes training with the SpamAssassin pilot configuration.
    """

    print_step("SA Pilot - Bayes Train")

    activate_spamassassin_config(PILOT_SA_BAYES_CONFIG_NAME)
    restart_spamassassin()

    run_spamassassin_training(
        dataset_split_dir=DATASET_SPLIT,
        output_root=PILOT_SA_BAYES_TRAINING_OUTPUT_DIR,
    )

    print_end("SA Pilot - Bayes Train")
