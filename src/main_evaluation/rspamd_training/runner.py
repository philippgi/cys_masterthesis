#!/usr/bin/env python3
"""
This module performs one reproducible Rspamd Bayes training run.

Workflow:
- Verify that the Rspamd and Redis docker containers are running
- Clear previous Bayes/statistics state
- Learn ham from data/datasets/split/train/ham
- Learn spam from data/datasets/split/train/spam
- Wait briefly and collect stable Rspamd stats
- Write a snapshot artifact with raw outputs and parsed counters
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    DATASET_SPLIT,
    OUTPUT_ROOT,
    RSPAMD_CONTAINER,
    RSPAMD_REDIS_CONTAINER,
    RSPAMD_TRAIN_HAM_CONTAINER_DIR,
    RSPAMD_TRAIN_SPAM_CONTAINER_DIR,
)

from src.utils.console import print_step, print_section, print_kv, print_end


def run_command(command: list[str]) -> subprocess.CompletedProcess:
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


def docker_exec_rspamd(*container_cmd: str) -> subprocess.CompletedProcess:
    return run_command(["docker", "exec", RSPAMD_CONTAINER, *container_cmd])


def docker_exec_redis(*container_cmd: str) -> subprocess.CompletedProcess:
    return run_command(["docker", "exec", RSPAMD_REDIS_CONTAINER, *container_cmd])


def ensure_container_running(container_name: str) -> None:
    result = run_command(
        [
            "docker",
            "ps",
            "--filter",
            f"name={container_name}",
            "--format",
            "{{.Names}}",
        ]
    )

    running_names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    if container_name not in running_names:
        raise RuntimeError(f"Container '{container_name}' is not running.")


def count_files(directory: Path) -> int:
    return sum(1 for p in directory.rglob("*") if p.is_file())


def parse_rspamc_stat(stat_output: str) -> dict[str, int]:
    spam_match = re.search(r"Statfile:\s+BAYES_SPAM.*?learned:\s+(\d+)", stat_output, re.DOTALL)
    ham_match = re.search(r"Statfile:\s+BAYES_HAM.*?learned:\s+(\d+)", stat_output, re.DOTALL)
    total_match = re.search(r"Total learns:\s+(\d+)", stat_output)

    return {
        "bayes_spam_learned": int(spam_match.group(1)) if spam_match else -1,
        "bayes_ham_learned": int(ham_match.group(1)) if ham_match else -1,
        "total_learns": int(total_match.group(1)) if total_match else -1,
    }


def get_stable_stat(max_attempts: int = 5, sleep_seconds: int = 2) -> subprocess.CompletedProcess:
    """
    Rspamd stats can occasionally lag directly after training.
    Retry a few times until Bayes counters become visible.
    """
    last_result: subprocess.CompletedProcess | None = None

    for _ in range(max_attempts):
        result = docker_exec_rspamd("rspamc", "stat")
        parsed = parse_rspamc_stat(result.stdout)

        if parsed["bayes_spam_learned"] >= 0 and parsed["bayes_ham_learned"] >= 0:
            if parsed["bayes_spam_learned"] > 0 or parsed["bayes_ham_learned"] > 0:
                return result

        last_result = result
        time.sleep(sleep_seconds)

    if last_result is None:
        raise RuntimeError("Failed to retrieve Rspamd statistics.")

    return last_result


def run_rspamd_training(
    output_root: Path | None = None,
    dataset_split_dir: Path | None = None,
) -> None:
    output_root = OUTPUT_ROOT if output_root is None else output_root
    dataset_split_dir = DATASET_SPLIT if dataset_split_dir is None else dataset_split_dir

    rspamd_output = output_root / "rspamd_training"
    training_snapshot_json = rspamd_output / "training_snapshot.json"
    training_snapshot_txt = rspamd_output / "training_snapshot.txt"

    train_ham_dir = dataset_split_dir / "train" / "ham"
    train_spam_dir = dataset_split_dir / "train" / "spam"

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

    rspamd_output.mkdir(parents=True, exist_ok=True)

    print_step("Rspamd Training")

    print_section("Training dataset")
    print_kv("ham_training_files", n_train_ham)
    print_kv("spam_training_files", n_train_spam)

    ensure_container_running(RSPAMD_CONTAINER)
    ensure_container_running(RSPAMD_REDIS_CONTAINER)

    print_section("Clearing previous Rspamd Bayes/statistics state")
    redis_flush_result = docker_exec_redis("redis-cli", "FLUSHDB")

    print_section("Resetting Rspamd statistics counters")
    stat_reset_result = docker_exec_rspamd("rspamc", "stat_reset")

    print_section("Learning ham corpus")
    ham_result = docker_exec_rspamd(
        "rspamc",
        "learn_ham",
        RSPAMD_TRAIN_HAM_CONTAINER_DIR,
    )

    print_section("Learning spam corpus")
    spam_result = docker_exec_rspamd(
        "rspamc",
        "learn_spam",
        RSPAMD_TRAIN_SPAM_CONTAINER_DIR,
    )

    print_section("Collecting version and Rspamd stats")

    try:
        version_result = docker_exec_rspamd("rspamd", "--version")
    except RuntimeError:
        version_result = docker_exec_rspamd("rspamd", "-V")

    stat_result = get_stable_stat()
    parsed_stat = parse_rspamc_stat(stat_result.stdout)

    timestamp_utc = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "timestamp_utc": timestamp_utc,
        "rspamd_container_name": RSPAMD_CONTAINER,
        "redis_container_name": RSPAMD_REDIS_CONTAINER,
        "train_ham_dir_host": str(train_ham_dir),
        "train_spam_dir_host": str(train_spam_dir),
        "train_ham_dir_container": RSPAMD_TRAIN_HAM_CONTAINER_DIR,
        "train_spam_dir_container": RSPAMD_TRAIN_SPAM_CONTAINER_DIR,
        "n_train_ham": n_train_ham,
        "n_train_spam": n_train_spam,
        "rspamd_version": version_result.stdout.strip(),
        "commands": {
            "redis_flushdb": f"docker exec {RSPAMD_REDIS_CONTAINER} redis-cli FLUSHDB",
            "stat_reset": f"docker exec {RSPAMD_CONTAINER} rspamc stat_reset",
            "learn_ham": f"docker exec {RSPAMD_CONTAINER} rspamc learn_ham {RSPAMD_TRAIN_HAM_CONTAINER_DIR}",
            "learn_spam": f"docker exec {RSPAMD_CONTAINER} rspamc learn_spam {RSPAMD_TRAIN_SPAM_CONTAINER_DIR}",
            "stat": f"docker exec {RSPAMD_CONTAINER} rspamc stat",
        },
        "stdout": {
            "redis_flushdb": redis_flush_result.stdout,
            "stat_reset": stat_reset_result.stdout,
            "learn_ham": ham_result.stdout,
            "learn_spam": spam_result.stdout,
            "stat": stat_result.stdout,
        },
        "stderr": {
            "redis_flushdb": redis_flush_result.stderr,
            "stat_reset": stat_reset_result.stderr,
            "learn_ham": ham_result.stderr,
            "learn_spam": spam_result.stderr,
            "stat": stat_result.stderr,
        },
        "parsed_stat": parsed_stat,
    }

    with open(training_snapshot_json, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    with open(training_snapshot_txt, "w", encoding="utf-8") as f:
        f.write("Rspamd Training Snapshot\n")
        f.write("=======================\n\n")
        f.write(f"Timestamp UTC: {timestamp_utc}\n")
        f.write(f"Rspamd container: {RSPAMD_CONTAINER}\n")
        f.write(f"Redis container: {RSPAMD_REDIS_CONTAINER}\n")
        f.write(f"Ham training files: {n_train_ham}\n")
        f.write(f"Spam training files: {n_train_spam}\n\n")
        f.write("Rspamd version:\n")
        f.write(version_result.stdout)
        f.write("\n\n")
        f.write("Parsed rspamc stat:\n")
        f.write(json.dumps(parsed_stat, indent=2))
        f.write("\n\n")
        f.write("Raw rspamc stat:\n")
        f.write(stat_result.stdout)

    print_section("Parsed Bayes stats")
    print_kv("bayes_spam_learned", parsed_stat["bayes_spam_learned"])
    print_kv("bayes_ham_learned", parsed_stat["bayes_ham_learned"])
    print_kv("total_learns", parsed_stat["total_learns"])

    print_section("Output files")
    print_kv("training_snapshot_json", training_snapshot_json)
    print_kv("training_snapshot_txt", training_snapshot_txt)

    print_end("Rspamd Training")