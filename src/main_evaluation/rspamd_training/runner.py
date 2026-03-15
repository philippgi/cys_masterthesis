#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess
import time
import sys

from tqdm import tqdm

from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section


def _reset_rspamd_state():
    """
    Remove Redis and Rspamd state so the neural classifier starts from
    a completely clean state.
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


def _wait_for_rspamd_ready(timeout: int = 30):
    """
    Wait until rspamd is ready to accept scan requests on /checkv2.
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
                "http://127.0.0.1:11333/checkv2",
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
    Train rspamd neural classifier via HTTP /checkv2 using ANN-Train header.
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
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-H",
                f"ANN-Train: {ann_class}",
                "--data-binary",
                f"@{path}",
                "http://127.0.0.1:11333/checkv2",
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


def run_rspamd_training():
    """
    RS3 training runner.

    Experiment:
        RS3 = Rules + Neural

    Workflow:
        1 Activate RS3 config
        2 Reset Redis + Rspamd state
        3 Restart rspamd
        4 Reset pipeline output
        5 Split dataset
        6 Wait until rspamd is ready
        7 Train neural classifier via HTTP
        8 Restart rspamd
        9 Wait until rspamd is ready again
    """
    print_step("RS3 Training (Rules + Neural)")

    activate_rspamd_config("rs3")
    _reset_rspamd_state()
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    train_spam_dir = dataset_dir / "train" / "spam"
    train_ham_dir = dataset_dir / "train" / "ham"

    reset_pipeline_output()
    run_dataset_split(train_ratio=0.8)

    _wait_for_rspamd_ready()

    _learn_directory(train_spam_dir, "spam")
    _learn_directory(train_ham_dir, "ham")

    restart_rspamd()
    _wait_for_rspamd_ready()


if __name__ == "__main__":
    run_rspamd_training()