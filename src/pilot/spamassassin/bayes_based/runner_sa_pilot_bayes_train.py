from __future__ import annotations

from config import BASE_DIR, DATASET_SPLIT
from src.main_evaluation.main_evaluation_utils.container_control import restart_spamassassin
from src.main_evaluation.main_evaluation_utils.sa_config_switcher import activate_spamassassin_config
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.utils.console import print_end, print_kv, print_section, print_step


OUTPUT_ROOT = BASE_DIR / "data/output/pilot/sa/bayes"


def run_sa_pilot_bayes_train() -> None:
    print_step("SA Pilot - Bayes Training")

    activate_spamassassin_config("sa_pilot_bayes.cf")
    restart_spamassassin()

    print_section("Training source")
    print_kv("dataset_split_dir", DATASET_SPLIT)
    print_kv("output_root", OUTPUT_ROOT)

    run_spamassassin_training(
        output_root=OUTPUT_ROOT,
        dataset_split_dir=DATASET_SPLIT,
    )

    print_end("SA Pilot - Bayes Training")


if __name__ == "__main__":
    run_sa_pilot_bayes_train()
