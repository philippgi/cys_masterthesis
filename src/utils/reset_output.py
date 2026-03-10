import shutil
from config import OUTPUT_ROOT, DATASET_SPLIT


def reset_pipeline_output():
    """
    Deletes all generated pipeline output.

    This removes the entire output directory used by the experiment
    pipeline so that the pipeline can be executed from a clean state.

    The directory is recreated afterwards to ensure that subsequent
    pipeline steps can write their artefacts without errors.
    """

    if OUTPUT_ROOT.exists():
        print(f"Deleting output directory: {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if DATASET_SPLIT.exists():
        print(f"Deleting output directory: {DATASET_SPLIT}")
        shutil.rmtree(DATASET_SPLIT)

    print("Pipeline output reset complete.")