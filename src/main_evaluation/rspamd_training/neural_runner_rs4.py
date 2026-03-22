#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess
import time
import sys
import random

from tqdm import tqdm
from config import BASE_DIR

from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.utils.console import print_step, print_section, print_kv
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage


# =============================
# INTERNAL HELPERS
# =============================

def _reset_rspamd_state():
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


def _learn_directory(files, ann_class: str):
    if ann_class not in {"spam", "ham"}:
        raise ValueError("ann_class must be 'spam' or 'ham'")

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


# =============================
# MAIN RS4 TRAINING
# =============================

def run_rspamd_neural_training_rs4(train_salt_ratio: float = 0.25):
    print_step(f"RS4 Training (ratio={train_salt_ratio})")

    # 👉 reproducibility
    random.seed(42)

    activate_rspamd_config("rs4")
    _reset_rspamd_state()
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    train_spam_dir = dataset_dir / "train" / "spam"
    train_ham_dir = dataset_dir / "train" / "ham"

    run_dataset_split(train_ratio=0.8)

    _wait_for_rspamd_ready()

    # =============================
    # SAMPLING
    # =============================

    spam_files = sorted(p for p in train_spam_dir.iterdir() if p.is_file())

    k = int(len(spam_files) * train_salt_ratio)
    sampled = set(random.sample(spam_files, k))
    remaining = [p for p in spam_files if p not in sampled]

    print_section("Sampling")
    print_kv("Total spam", len(spam_files))
    print_kv("Selected for salting", len(sampled))
    print_kv("Remaining clean", len(remaining))

    # =============================
    # TRIGGER PIPELINE
    # =============================

    rs4_output = BASE_DIR / f"data/output/RS4_{int(train_salt_ratio*100)}/train"

    run_trigger_vocabulary(
        output_root=rs4_output,
        dataset_split_dir=dataset_dir,
    )

    run_trigger_coverage(
        output_root=rs4_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="broad",
        dataset_type="train",
    )

    # =============================
    # SALTING (TRAIN DATA)
    # =============================

    rs4_output = BASE_DIR / f"data/output/RS4_{int(train_salt_ratio*100)}/train"

    run_salted_email_generator(
        output_root=rs4_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="broad",
        subject_max_insertions=1,
        body_max_insertions=20,
        salt_mode="fragment",
        insert_after_index=2,
        fragment_max_positions=None,
        dataset_type="train",
    )

    salted_dir = rs4_output / "salted_email_generator" / "emails"
    salted_files = sorted(p for p in salted_dir.iterdir() if p.is_file())

    sampled_ids = {p.stem for p in sampled}

    salted_map = {}
    for f in salted_files:
        salted_id = f.name.split("__")[0]
        if salted_id in sampled_ids and salted_id not in salted_map:
            salted_map[salted_id] = f

    salted_selected = list(salted_map.values())

    print_section("Salting result")
    print_kv("Salted generated", len(salted_files))
    print_kv("Salted used", len(salted_selected))

    # =============================
    # FINAL TRAIN SET
    # =============================

    final_spam = remaining + salted_selected
    ham_files = sorted(p for p in train_ham_dir.iterdir() if p.is_file())

    print_section("Final training dataset")
    print_kv("Spam total", len(final_spam))
    print_kv("Ham total", len(ham_files))

    # =============================
    # TRAIN
    # =============================

    _learn_directory(final_spam, "spam")
    _learn_directory(ham_files, "ham")

    restart_rspamd()
    _wait_for_rspamd_ready()