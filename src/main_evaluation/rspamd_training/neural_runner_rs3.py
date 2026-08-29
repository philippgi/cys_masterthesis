#!/usr/bin/env python3
"""
Trains the Rspamd neural classifier for experiment RS3.

The training run activates the RS3 configuration, resets persisted Rspamd state,
creates the reproducible dataset split, submits spam and ham training messages
with the ANN-Train header, and restarts Rspamd before evaluation.
"""

from pathlib import Path
import shutil
import subprocess
import time
import sys

from tqdm import tqdm
from config import BASE_DIR, RSPAMD_HOST, RSPAMD_PORT

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section


def _reset_rspamd_state():
    """
    Remove persisted Redis and Rspamd state before neural training.
    """

    redis_dir = BASE_DIR / "docker/redis"
    rspamd_state_dir = BASE_DIR / "docker/rspamd-state"

    print_section("Resetting Redis and Rspamd state")

    # Remove previously learned Redis state to ensure an independent training run.
    if redis_dir.exists():
        shutil.rmtree(redis_dir)
    redis_dir.mkdir(parents=True, exist_ok=True)

    # Remove persisted Rspamd state from previous neural models.
    if rspamd_state_dir.exists():
        shutil.rmtree(rspamd_state_dir)
    rspamd_state_dir.mkdir(parents=True, exist_ok=True)


def _wait_for_rspamd_ready(timeout: int = 30):
    """
    Wait until Rspamd accepts scan requests on the /checkv2 endpoint.

    Args:
        timeout (int): Maximum number of readiness checks.

    Raises:
        RuntimeError: If Rspamd does not become ready within the timeout.
    """

    print_section("Waiting for Rspamd to become ready")

    # Use a training message as a probe for the normal Rspamd scan endpoint.
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


def _learn_directory(directory: Path, ann_class: str):
    """
    Train the Rspamd neural classifier with all messages of one class.

    Args:
        directory (Path): Directory containing the training messages.
        ann_class (str): Neural training class, either "spam" or "ham".

    Raises:
        ValueError: If an unsupported neural training class is provided.
        RuntimeError: If a training request fails.
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
        # Assign each submitted message to its neural training class via ANN-Train.
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


def run_rspamd_neural_training():
    """
    Train the Rspamd neural classifier for the RS3 Rules + Neural experiment.
    """

    print_step("RS3 Training (Rules + Neural)")

    # Activate RS3 and start neural training from a clean persisted state.
    activate_rspamd_config("rs3")
    _reset_rspamd_state()
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    train_spam_dir = dataset_dir / "train" / "spam"
    train_ham_dir = dataset_dir / "train" / "ham"

    # Recreate the reproducible 80/20 dataset split used for RS3.
    run_dataset_split(train_ratio=0.8)

    _wait_for_rspamd_ready()

    # Train both classes separately using the unchanged training messages.
    _learn_directory(train_spam_dir, "spam")
    _learn_directory(train_ham_dir, "ham")

    # Restart Rspamd so the trained neural model is available for evaluation.
    restart_rspamd()
    _wait_for_rspamd_ready()


if __name__ == "__main__":
    run_rspamd_neural_training()