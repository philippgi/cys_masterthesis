#!/usr/bin/env python3
"""
This module performs one reproducible SpamAssassin Bayes training run.

Workflow:
1) Verify that the SpamAssassin container is running
2) Clear previous Bayes state
3) Learn ham from /split/train/ham
4) Learn spam from /split/train/spam
5) Sync Bayes database
6) Dump Bayes stats and write a snapshot artifact

The training data is expected to be mounted into the container as:
    /split/train/ham
    /split/train/spam
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import DATASET_SPLIT, OUTPUT_DIR


SPAMASSASSIN_CONTAINER = "thesis-lab-spamassassin"
SPAMASSASSIN_ARTIFACT_DIR = OUTPUT_DIR.parent / "spamassassin_training"
TRAINING_SNAPSHOT_JSON = SPAMASSASSIN_ARTIFACT_DIR / "training_snapshot.json"
TRAINING_SNAPSHOT_TXT = SPAMASSASSIN_ARTIFACT_DIR / "training_snapshot.txt"


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    """
    Runs a subprocess command and raises an exception on failure.
    """
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"{' '.join(command)}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


def docker_exec(*container_cmd: str) -> subprocess.CompletedProcess:
    """
    Executes a command inside the SpamAssassin container.
    """
    return run_command(
        ["docker", "exec", SPAMASSASSIN_CONTAINER, *container_cmd]
    )


def ensure_container_running() -> None:
    """
    Verifies that the configured SpamAssassin container is running.
    """
    result = run_command(
        [
            "docker",
            "ps",
            "--filter",
            f"name={SPAMASSASSIN_CONTAINER}",
            "--format",
            "{{.Names}}",
        ]
    )

    running_names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if SPAMASSASSIN_CONTAINER not in running_names:
        raise RuntimeError(
            f"SpamAssassin container '{SPAMASSASSIN_CONTAINER}' is not running."
        )


def count_files(directory: Path) -> int:
    """
    Counts regular files in a directory.
    """
    return sum(1 for p in directory.iterdir() if p.is_file())


def run_spamassassin_training() -> None:
    """
    Runs a full reproducible Bayes training cycle and stores a snapshot artifact.
    """
    train_ham_dir = DATASET_SPLIT / "train" / "ham"
    train_spam_dir = DATASET_SPLIT / "train" / "spam"

    if not train_ham_dir.exists():
        raise FileNotFoundError(f"Missing ham training directory: {train_ham_dir}")
    if not train_spam_dir.exists():
        raise FileNotFoundError(f"Missing spam training directory: {train_spam_dir}")

    n_train_ham = count_files(train_ham_dir)
    n_train_spam = count_files(train_spam_dir)

    if n_train_ham == 0:
        raise ValueError(f"No ham files found in: {train_ham_dir}")
    if n_train_spam == 0:
        raise ValueError(f"No spam files found in: {train_spam_dir}")

    SPAMASSASSIN_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    print("--> Starting SpamAssassin training <--")
    print(f"Container: {SPAMASSASSIN_CONTAINER}")
    print(f"Ham training files:  {n_train_ham}")
    print(f"Spam training files: {n_train_spam}")

    ensure_container_running()

    # 1) Clear Bayes state to guarantee reproducibility
    print("Clearing previous Bayes state ...")
    clear_result = docker_exec("sa-learn", "--clear")

    # 2) Learn ham
    print("Learning ham corpus ...")
    ham_result = docker_exec("sa-learn", "--ham", "/split/train/ham")

    # 3) Learn spam
    print("Learning spam corpus ...")
    spam_result = docker_exec("sa-learn", "--spam", "/split/train/spam")

    # 4) Sync Bayes database
    print("Syncing Bayes database ...")
    sync_result = docker_exec("sa-learn", "--sync")

    # 5) Collect version and Bayes stats
    print("Collecting SpamAssassin version and Bayes stats ...")
    version_result = docker_exec("spamassassin", "--version")
    dump_magic_result = docker_exec("sa-learn", "--dump", "magic")

    timestamp_utc = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "timestamp_utc": timestamp_utc,
        "container_name": SPAMASSASSIN_CONTAINER,
        "train_ham_dir_host": str(train_ham_dir),
        "train_spam_dir_host": str(train_spam_dir),
        "train_ham_dir_container": "/split/train/ham",
        "train_spam_dir_container": "/split/train/spam",
        "n_train_ham": n_train_ham,
        "n_train_spam": n_train_spam,
        "spamassassin_version": version_result.stdout.strip(),
        "commands": {
            "clear": "docker exec thesis-lab-spamassassin sa-learn --clear",
            "learn_ham": "docker exec thesis-lab-spamassassin sa-learn --ham /split/train/ham",
            "learn_spam": "docker exec thesis-lab-spamassassin sa-learn --spam /split/train/spam",
            "sync": "docker exec thesis-lab-spamassassin sa-learn --sync",
            "dump_magic": "docker exec thesis-lab-spamassassin sa-learn --dump magic",
        },
        "stdout": {
            "clear": clear_result.stdout,
            "learn_ham": ham_result.stdout,
            "learn_spam": spam_result.stdout,
            "sync": sync_result.stdout,
            "dump_magic": dump_magic_result.stdout,
        },
        "stderr": {
            "clear": clear_result.stderr,
            "learn_ham": ham_result.stderr,
            "learn_spam": spam_result.stderr,
            "sync": sync_result.stderr,
            "dump_magic": dump_magic_result.stderr,
        },
    }

    with open(TRAINING_SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    with open(TRAINING_SNAPSHOT_TXT, "w", encoding="utf-8") as f:
        f.write("SpamAssassin Training Snapshot\n")
        f.write("=============================\n\n")
        f.write(f"Timestamp UTC: {timestamp_utc}\n")
        f.write(f"Container: {SPAMASSASSIN_CONTAINER}\n")
        f.write(f"Ham training files: {n_train_ham}\n")
        f.write(f"Spam training files: {n_train_spam}\n\n")
        f.write("SpamAssassin version:\n")
        f.write(version_result.stdout)
        f.write("\n\n")
        f.write("sa-learn --dump magic:\n")
        f.write(dump_magic_result.stdout)

    print("\nTraining completed successfully.")
    print(f"Snapshot JSON: {TRAINING_SNAPSHOT_JSON}")
    print(f"Snapshot TXT:  {TRAINING_SNAPSHOT_TXT}")