#!/usr/bin/env python3
"""
Splits the SpamAssassin Public Corpus into reproducible training and test sets.

Ham and spam subsets are collected separately, shuffled using the configured
random seed, and copied into the generated train/test directory structure.
"""

import os
import shutil
import random

from config import DATASET_ROOT, DATASET_SPLIT, TRAIN_RATIO, RANDOM_SEED
from src.utils.console import print_step, print_section, print_kv, print_end, print_warning


# =============================
# HELPER FUNCTIONS
# =============================

def collect_files(folder):
    """
    Collect all files from a dataset directory in deterministic order.

    Args:
        folder: Source directory containing email files.

    Returns:
        list[str]: Sorted file paths.
    """

    files = []

    for f in os.listdir(folder):
        path = os.path.join(folder, f)
        if os.path.isfile(path):
            files.append(path)

    files.sort()
    return files


def split_files(files, train_ratio):
    """
    Split a file list into training and test subsets.

    Args:
        files (list[str]): Files to partition.
        train_ratio (float): Fraction assigned to the training set.

    Returns:
        tuple[list[str], list[str]]: Training and test file lists.
    """

    random.shuffle(files)
    split_index = int(len(files) * train_ratio)

    return files[:split_index], files[split_index:]


def copy_files(files, target_dir):
    """
    Copy email files into a target directory.

    Args:
        files (list[str]): Source file paths.
        target_dir: Destination directory.
    """

    os.makedirs(target_dir, exist_ok=True)

    for f in files:
        filename = os.path.basename(f)
        shutil.copy2(f, os.path.join(target_dir, filename))


# =============================
# MAIN FUNCTIONS
# =============================

def run_dataset_split(train_ratio=None, dataset_split_dir=None):
    """
    Create the configured ham/spam training and test dataset split.

    Args:
        train_ratio (float | None): Training fraction, or the configured default.
        dataset_split_dir: Output directory for the generated split.
    """

    train_ratio = TRAIN_RATIO if train_ratio is None else train_ratio
    dataset_split_dir = dataset_split_dir or DATASET_SPLIT

    # Remove any previous split so no stale files remain when the ratio changes
    if os.path.exists(dataset_split_dir):
        shutil.rmtree(dataset_split_dir)

    random.seed(RANDOM_SEED)
    ham_files = []
    spam_files = []

    ham_sources = [
        os.path.join(DATASET_ROOT, "easy_ham"),
        os.path.join(DATASET_ROOT, "easy_ham_2"),
    ]

    spam_sources = [
        os.path.join(DATASET_ROOT, "spam"),
        os.path.join(DATASET_ROOT, "spam_2"),
    ]

    for src in ham_sources:
        ham_files.extend(collect_files(src))

    for src in spam_sources:
        spam_files.extend(collect_files(src))

    print_step("Dataset Split")

    print_section("Input corpus size")
    print_kv("Ham emails", len(ham_files))
    print_kv("Spam emails", len(spam_files))

    # Split files or activate full-dataset mode
    if train_ratio == 1.0:
        ham_train = ham_files
        ham_test = ham_files
        spam_train = spam_files
        spam_test = spam_files

        print_warning("Full-dataset mode enabled -> Train and test both contain the complete dataset.")

    else:
        ham_train, ham_test = split_files(ham_files, train_ratio)
        spam_train, spam_test = split_files(spam_files, train_ratio)

    print_section("\nTrain/Test split result")
    print_kv("ham_train", len(ham_train))
    print_kv("ham_test", len(ham_test))
    print_kv("spam_train", len(spam_train))
    print_kv("spam_test", len(spam_test))

    train_ham_dir = os.path.join(dataset_split_dir, "train/ham")
    train_spam_dir = os.path.join(dataset_split_dir, "train/spam")
    test_ham_dir = os.path.join(dataset_split_dir, "test/ham")
    test_spam_dir = os.path.join(dataset_split_dir, "test/spam")

    copy_files(ham_train, train_ham_dir)
    copy_files(spam_train, train_spam_dir)
    copy_files(ham_test, test_ham_dir)
    copy_files(spam_test, test_spam_dir)

    print_end("Dataset Split")
