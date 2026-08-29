#!/usr/bin/env python3
"""
Trains the Rspamd neural classifier for experiment RS4.

A reproducible fraction of spam training emails is selected for adversarial
replacement. For each selected email, one generated salted variant is used
when available; otherwise the original message is retained. This preserves
the original training-set size and class balance.
"""

from pathlib import Path
import shutil
import subprocess
import time
import sys
import random

from tqdm import tqdm
from config import BASE_DIR, RSPAMD_HOST, RSPAMD_PORT, RANDOM_SEED

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


def _learn_directory(files, ann_class: str):
    """
    Train the Rspamd neural classifier with the provided messages.

    Args:
        files: Training message paths.
        ann_class (str): Neural training class, either "spam" or "ham".

    Raises:
        ValueError: If an unsupported neural training class is provided.
        RuntimeError: If a training request fails.
    """

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


# =============================
# MAIN RS4 TRAINING
# =============================

def run_rspamd_neural_training_rs4(train_salt_ratio: float = 0.25):
    """
    Train the adversarially retrained Rspamd neural model for RS4.

    Args:
        train_salt_ratio (float): Fraction of spam training emails selected
        for replacement by salted variants.
    """

    print_step(f"RS4 Training (ratio={train_salt_ratio})")

    # Seed all sampling and variant selection to make RS4 training reproducible.
    random.seed(RANDOM_SEED)

    # Activate RS4 and start training from a clean persisted state.
    activate_rspamd_config("rs4")
    _reset_rspamd_state()
    restart_rspamd()

    dataset_dir = BASE_DIR / "data/datasets/split"
    train_spam_dir = dataset_dir / "train" / "spam"
    train_ham_dir = dataset_dir / "train" / "ham"

    # Recreate the same reproducible 80/20 dataset split used by the evaluation.
    run_dataset_split(train_ratio=0.8)

    _wait_for_rspamd_ready()

    # =============================
    # SAMPLING
    # =============================

    # Select the configured fraction of spam training emails for adversarial replacement.
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

    # Build the trigger vocabulary and coverage data required for training-set salting.
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

    # Generate broad-vocabulary salted variants from the spam training set.
    run_salted_email_generator(
        output_root=rs4_output,
        dataset_split_dir=dataset_dir,
        salting_vocabulary="broad",
        subject_max_insertions=1,
        body_max_insertions=3,
        salt_mode="single",
        insert_after_index=2,
        fragment_max_positions=None,
        dataset_type="train",
    )

    salted_dir = rs4_output / "salted_email_generator" / "emails"
    salted_files = sorted(p for p in salted_dir.iterdir() if p.is_file())

    # Group generated salted variants by their original training message.
    variants_by_id = {}
    for f in salted_files:
        variants_by_id.setdefault(f.name.split("__")[0], []).append(f)

    # Replace each sampled spam email with exactly one randomly selected salted variant.
    # If no variant exists, retain the original email to preserve dataset size and class balance.
    salted_selected = []
    kept_unsalted = []
    for p in sorted(sampled):
        variants = variants_by_id.get(p.stem)
        if variants:
            salted_selected.append(random.choice(sorted(variants)))
        else:
            kept_unsalted.append(p)

    print_section("Salting result")
    print_kv("Salted generated", len(salted_files))
    print_kv("Salted used", len(salted_selected))
    print_kv("Sampled without variant (kept unsalted)", len(kept_unsalted))

    # =============================
    # FINAL TRAIN SET
    # =============================

    # Recombine untouched, salted, and unsaltable spam into a fixed-size training set.
    final_spam = remaining + salted_selected + kept_unsalted
    ham_files = sorted(p for p in train_ham_dir.iterdir() if p.is_file())

    print_section("Final training dataset")
    print_kv("Spam total", len(final_spam))
    print_kv("Ham total", len(ham_files))

    # =============================
    # TRAIN
    # =============================

    # Train the neural classifier on the modified spam set and unchanged ham set.
    _learn_directory(final_spam, "spam")
    _learn_directory(ham_files, "ham")

    # Restart Rspamd so the retrained neural model is available for evaluation.
    restart_rspamd()
    _wait_for_rspamd_ready()