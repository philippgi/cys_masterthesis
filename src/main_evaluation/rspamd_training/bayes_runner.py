#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

from config import (
    RSPAMD_CONTAINER,
    RSPAMD_REDIS_CONTAINER,
    RSPAMD_TRAIN_HAM_CONTAINER_DIR,
    RSPAMD_TRAIN_SPAM_CONTAINER_DIR,
    RSPAMD_HOST,
    RSPAMD_PORT,
    RSPAMD_TIMEOUT,
)
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section, print_kv


def _count_files(directory: Path) -> int:
    return sum(1 for p in directory.iterdir() if p.is_file())


def _wait_for_rspamd_ready(timeout: int = RSPAMD_TIMEOUT):
    print_section("Waiting for Rspamd to become ready")

    for _ in range(timeout):
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--max-time",
                "5",
                f"http://{RSPAMD_HOST}:{RSPAMD_PORT}/ping",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0 and "pong" in result.stdout.lower():
            print_section("Rspamd is ready")
            return

        time.sleep(1)

    raise RuntimeError(
        f"Rspamd did not become ready in time on http://{RSPAMD_HOST}:{RSPAMD_PORT}"
    )


def _reset_bayes():
    print_section("Resetting Bayes data")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            RSPAMD_REDIS_CONTAINER,
            "redis-cli",
            "FLUSHALL",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Failed to reset Bayes data\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    print_kv("redis_flushall", result.stdout.strip())


def _parse_learned_value(stat_output: str, statfile_name: str) -> int:
    for line in stat_output.splitlines():
        if f"Statfile: {statfile_name} " in line:
            marker = "learned:"
            if marker not in line:
                raise RuntimeError(
                    f"'learned:' not found in stat line for {statfile_name}: {line}"
                )

            tail = line.split(marker, 1)[1].strip()
            value = tail.split(";", 1)[0].strip()
            return int(value)

    raise RuntimeError(f"Statfile {statfile_name} not found in rspamc stat output")


def _get_bayes_counters() -> dict[str, int]:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            RSPAMD_CONTAINER,
            "rspamc",
            "stat",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "rspamc stat failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    bayes_spam = _parse_learned_value(result.stdout, "BAYES_SPAM")
    bayes_ham = _parse_learned_value(result.stdout, "BAYES_HAM")

    return {
        "bayes_spam": bayes_spam,
        "bayes_ham": bayes_ham,
        "total": bayes_spam + bayes_ham,
    }


def _print_bayes_counter_snapshot(title: str, counters: dict[str, int]):
    print_section(title)
    print_kv("bayes_spam", counters["bayes_spam"])
    print_kv("bayes_ham", counters["bayes_ham"])
    print_kv("total", counters["total"])


def _print_bayes_counter_delta(
    title: str,
    before: dict[str, int],
    after: dict[str, int],
):
    print_section(title)
    print_kv("delta_spam", after["bayes_spam"] - before["bayes_spam"])
    print_kv("delta_ham", after["bayes_ham"] - before["bayes_ham"])
    print_kv("delta_total", after["total"] - before["total"])


def _learn_directory_bayes(
    host_directory: Path,
    container_directory: str,
    bayes_class: str,
):
    if bayes_class not in {"spam", "ham"}:
        raise ValueError("bayes_class must be 'spam' or 'ham'")

    files = sorted(p for p in host_directory.iterdir() if p.is_file())

    print_section(f"Bayes training: {bayes_class} ({len(files)} messages)")

    failed = 0

    for path in tqdm(
        files,
        desc=f"Bayes {bayes_class}",
        unit="mail",
        colour="green",
        file=sys.stdout,
    ):
        container_file = f"{container_directory}/{path.name}"

        cmd = (
            f"rspamc learn_{bayes_class} < '{container_file}'"
        )

        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                RSPAMD_CONTAINER,
                "sh",
                "-c",
                cmd,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            failed += 1
            print_section(f"Bayes learn failed for {path.name}")
            print_kv("container_file", container_file)
            print_kv("returncode", result.returncode)
            print_kv("stdout", result.stdout.strip())
            print_kv("stderr", result.stderr.strip())

    print_section("Bayes training summary")
    print_kv("class", bayes_class)
    print_kv("files", len(files))
    print_kv("failed", failed)

    if failed > 0:
        raise RuntimeError(
            f"Bayes training had {failed} failed messages for class={bayes_class}"
        )


def _print_bayes_stats():
    print_section("Rspamd Bayes stats")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            RSPAMD_CONTAINER,
            "rspamc",
            "stat",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "rspamc stat failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    print(result.stdout)


def run_rspamd_bayes_training(dataset_split_dir: Path):
    print_step("Rspamd Bayes Training")

    train_spam_dir = dataset_split_dir / "train" / "spam"
    train_ham_dir = dataset_split_dir / "train" / "ham"

    expected_spam = _count_files(train_spam_dir)
    expected_ham = _count_files(train_ham_dir)

    print_section("Bayes training input")
    print_kv("train_spam_dir", train_spam_dir)
    print_kv("train_ham_dir", train_ham_dir)
    print_kv("expected_spam_files", expected_spam)
    print_kv("expected_ham_files", expected_ham)
    print_kv("container_spam_dir", RSPAMD_TRAIN_SPAM_CONTAINER_DIR)
    print_kv("container_ham_dir", RSPAMD_TRAIN_HAM_CONTAINER_DIR)

    _wait_for_rspamd_ready()

    _reset_bayes()
    restart_rspamd()
    _wait_for_rspamd_ready()

    counters_before = _get_bayes_counters()
    _print_bayes_counter_snapshot("Bayes counters before learning", counters_before)

    _learn_directory_bayes(
        host_directory=train_spam_dir,
        container_directory=RSPAMD_TRAIN_SPAM_CONTAINER_DIR,
        bayes_class="spam",
    )

    counters_after_spam = _get_bayes_counters()
    _print_bayes_counter_snapshot(
        "Bayes counters after spam learning",
        counters_after_spam,
    )
    _print_bayes_counter_delta(
        "Bayes delta after spam learning",
        counters_before,
        counters_after_spam,
    )

    _learn_directory_bayes(
        host_directory=train_ham_dir,
        container_directory=RSPAMD_TRAIN_HAM_CONTAINER_DIR,
        bayes_class="ham",
    )

    counters_after_ham = _get_bayes_counters()
    _print_bayes_counter_snapshot(
        "Bayes counters after ham learning",
        counters_after_ham,
    )
    _print_bayes_counter_delta(
        "Bayes delta after ham learning",
        counters_after_spam,
        counters_after_ham,
    )
    _print_bayes_counter_delta(
        "Bayes total delta",
        counters_before,
        counters_after_ham,
    )

    actual_spam_delta = counters_after_spam["bayes_spam"] - counters_before["bayes_spam"]
    actual_ham_delta = counters_after_ham["bayes_ham"] - counters_after_spam["bayes_ham"]

    print_section("Bayes learning validation")
    print_kv("expected_spam_files", expected_spam)
    print_kv("actual_spam_delta", actual_spam_delta)
    print_kv("missing_spam", expected_spam - actual_spam_delta)
    print_kv("expected_ham_files", expected_ham)
    print_kv("actual_ham_delta", actual_ham_delta)
    print_kv("missing_ham", expected_ham - actual_ham_delta)

    _print_bayes_stats()

    restart_rspamd()
    _wait_for_rspamd_ready()