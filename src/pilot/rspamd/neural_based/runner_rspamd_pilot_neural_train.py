#!/usr/bin/env python3
"""
Trains the Rspamd neural classifier for the neural pilot study.

Existing Redis and Rspamd state is reset before training. Spam and ham messages
from the training split are then submitted to Rspamd with the corresponding
ANN training class.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

from config import (
    BASE_DIR,
    RSPAMD_HOST,
    RSPAMD_PORT,
    TRAIN_RATIO,
    PILOT_RS_NEURAL_CONFIG_NAME,
)
from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.utils.console import print_step, print_section, print_end


def _reset_rspamd_state() -> None:
    """
    Remove persisted Redis and Rspamd state before neural training.
    """

    redis_dir = BASE_DIR / "docker/redis"
    rspamd_state_dir = BASE_DIR / "docker/rspamd-state"

    print_section("Resetting Redis and Rspamd state")

    if redis_dir.exists():
        shutil.rmtree(redis_dir)
    redis_dir.mkdir(parents=True, exist_ok=True)

    if rspamd_state_dir.exists():
        shutil.rmtree(rspamd_state_dir)
    rspamd_state_dir.mkdir(parents=True, exist_ok=True)


def _wait_for_rspamd_ready(timeout: int = 30) -> None:
    """
    Wait until Rspamd accepts scan requests.

    Args:
        timeout (int): Maximum number of readiness checks.
    """

    print_section("Waiting for Rspamd to become ready")

    test_file = BASE_DIR / "data/datasets/split/train/spam/00001.317e78fa8ee2f54cd4890fdc09ba8176"

    for _ in range(timeout):
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--max-time",
                "5",
                "--data-binary",
                f"@{test_file}",
                f"http://{RSPAMD_HOST}:{RSPAMD_PORT}/checkv2",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if result.returncode == 0:
            print_section("Rspamd is ready.")
            return

        time.sleep(1)

    raise RuntimeError("Rspamd did not become ready in time")


def _learn_directory(directory: Path, ann_class: str) -> None:
    """
    Submit all messages in a directory for neural training.

    Args:
        directory (Path): Directory containing training messages.
        ann_class (str): Neural training class, either spam or ham.

    Raises:
        ValueError: If an unsupported training class is provided.
        RuntimeError: If a message cannot be submitted successfully.
    """

    if ann_class not in {"spam", "ham"}:
        raise ValueError("ann_class must be 'spam' or 'ham'")

    files = sorted(p for p in directory.iterdir() if p.is_file())

    print_section(f"Neural training: {ann_class} ({len(files)} messages)")

    for path in tqdm(
        files,
        desc=f"Neural {ann_class}",
        unit="mail",
        colour="green",
        file=sys.stdout,
    ):
        # ANN-Train assigns the submitted message to the selected neural training class.
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-H",
                f"ANN-Train: {ann_class}",
                "--data-binary",
                f"@{path}",
                f"http://{RSPAMD_HOST}:{RSPAMD_PORT}/checkv2",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Neural training failed for {path.name}, class={ann_class}\n"
                f"{result.stderr}"
            )


def run_rspamd_pilot_neural_train() -> None:
    """
    Reset the neural state and train Rspamd on the spam and ham training sets.
    """

    print_step("Rspamd Pilot - Neural Train")

    activate_rspamd_config(PILOT_RS_NEURAL_CONFIG_NAME)
    _reset_rspamd_state()
    restart_rspamd()

    run_dataset_split(train_ratio=TRAIN_RATIO)

    dataset_dir = BASE_DIR / "data/datasets/split"
    train_spam_dir = dataset_dir / "train" / "spam"
    train_ham_dir = dataset_dir / "train" / "ham"

    _wait_for_rspamd_ready()

    _learn_directory(train_spam_dir, "spam")
    _learn_directory(train_ham_dir, "ham")

    restart_rspamd()
    _wait_for_rspamd_ready()

    print_end("Rspamd Pilot - Neural Train")


if __name__ == "__main__":
    run_rspamd_pilot_neural_train()