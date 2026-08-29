"""
Provides a helper for resetting generated experiment output.

The pipeline output and dataset split directories are removed and recreated
to ensure a clean state before a new experiment run.
"""

import shutil
from config import OUTPUT_ROOT, DATASET_SPLIT


def reset_pipeline_output():
    """
    Remove and recreate all generated pipeline output directories.
    """

    if OUTPUT_ROOT.exists():
        print(f"Deleting output directory: {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if DATASET_SPLIT.exists():
        print(f"Deleting dataset split directory: {DATASET_SPLIT}")
        shutil.rmtree(DATASET_SPLIT)

    DATASET_SPLIT.mkdir(parents=True, exist_ok=True)

    print("Pipeline output reset complete.")