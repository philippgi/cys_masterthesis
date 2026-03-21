from __future__ import annotations

from config import DATASET_SPLIT, OUTPUT_ROOT
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.utils.console import print_end, print_step


def run_sa_pilot_bayes_train() -> None:
    print_step("SA Pilot - Bayes Train")

    activate_spamassassin_config("sa_pilot_bayes.cf")
    restart_spamassassin()

    run_spamassassin_training(
        dataset_split_dir=DATASET_SPLIT,
        output_root=OUTPUT_ROOT / "pilot_sa_bayes",
    )

    print_end("SA Pilot - Bayes Train")
