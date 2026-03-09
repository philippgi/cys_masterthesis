#!/usr/bin/env python3
"""
This script partitions the SpamAssassin corpus into training and test datasets.

It assumes that:
- the SpamAssassin corpus subsets are stored in the directory datasets/spamassassin_corpus/
  'easy_ham', 'easy_ham_2', 'spam', and 'spam_2'
- ham subsets represent legitimate emails
- spam subsets represent unsolicited emails

The script performs a stratified dataset train:
- ham and spam messages are treated independently
- 80% of each class are assigned to the training set
- 20% are assigned to the test set

The resulting directory structure is:

train/
    ham/
    spam/
test/
    ham/
    spam/
"""

import os
import shutil
import random
from config import DATASET_ROOT, DATASET_SPLIT, TRAIN_RATIO, RANDOM_SEED

# =============================
# HELPER FUNCTIONS
# =============================


def collect_files(folder):
    """
    Collect all email files from a given directory.
    Only regular files are included. Subdirectories are ignored.

    Args:
        folder (str): Directory to scan for email files.

    Returns:
        list[str]: List of file paths.
    """
    files = []

    for f in os.listdir(folder):
        path = os.path.join(folder, f)
        if os.path.isfile(path):
            files.append(path)

    return files


def split_files(files, train_ratio):
    """
    Split a list of files into training and test subsets.

    The file order is randomized using a deterministic
    shuffle based on the configured random seed.

    Args:
        files (list[str]): List of file paths.
        train_ratio (float): Fraction of files assigned to training.

    Returns:
        tuple(list[str], list[str]): training_files, test_files
    """
    random.shuffle(files)
    split_index = int(len(files) * train_ratio)

    return files[:split_index], files[split_index:]


def copy_files(files, target_dir):
    """
    Copy email files into the specified target directory.

    The directory will be created if it does not exist.

    Args:
        files (list[str]): List of file paths to copy.
        target_dir (str): Output directory.
    """
    os.makedirs(target_dir, exist_ok=True)

    for f in files:
        filename = os.path.basename(f)
        shutil.copy2(f, os.path.join(target_dir, filename))


def run_dataset_split():
    """
    Orchestrates dataset collection, partitioning, and export.

    Steps:
    1) Collect ham and spam emails from the Folder datasets/spamassassin_corpus/..
    2) Perform a stratified 80/20 train/test train
    3) Copy files into the output directory structure
    4) Print dataset statistics for documentation
    """

    # Initialize random number generator with fixed seed
    random.seed(RANDOM_SEED)

    # =============================
    # DATASET COLLECTION
    # =============================

    # Ham subsets from the SpamAssassin corpus
    ham_sources = [
        os.path.join(DATASET_ROOT, "easy_ham"),
        os.path.join(DATASET_ROOT, "easy_ham_2"),
    ]

    # Spam subsets from the SpamAssassin corpus
    spam_sources = [
        os.path.join(DATASET_ROOT, "spam"),
        os.path.join(DATASET_ROOT, "spam_2"),
    ]

    ham_files = []
    spam_files = []

    # Aggregate ham emails
    for src in ham_sources:
        ham_files.extend(collect_files(src))

    # Aggregate spam emails
    for src in spam_sources:
        spam_files.extend(collect_files(src))

    print("--> Starting Dataset Split <--")
    print("\nSpamAssassin corpus size: ")
    print(f"* Ham emails: {len(ham_files)}")
    print(f"* Spam emails: {len(spam_files)}")

    # =============================
    # DATASET PARTITIONING
    # =============================

    # Perform stratified train:
    # ham and spam are train independently to preserve class distribution
    ham_train, ham_test = split_files(ham_files, TRAIN_RATIO)
    spam_train, spam_test = split_files(spam_files, TRAIN_RATIO)

    print("\nSplit results:")
    print(f"* Ham train: {len(ham_train)}")
    print(f"* Ham test: {len(ham_test)}")
    print(f"* Spam train: {len(spam_train)}")
    print(f"* Spam test: {len(spam_test)}")

    # =============================
    # OUTPUT DIRECTORY STRUCTURE
    # =============================

    # Training dataset directories
    train_ham_dir = os.path.join(DATASET_SPLIT, "train/ham")
    train_spam_dir = os.path.join(DATASET_SPLIT, "train/spam")

    # Test dataset directories
    test_ham_dir = os.path.join(DATASET_SPLIT, "test/ham")
    test_spam_dir = os.path.join(DATASET_SPLIT, "test/spam")

    # Copy files into their respective directories
    copy_files(ham_train, train_ham_dir)
    copy_files(spam_train, train_spam_dir)

    copy_files(ham_test, test_ham_dir)
    copy_files(spam_test, test_spam_dir)

    print("\n--> Dataset split completed <--")