#!/usr/bin/env python3
"""
Sequential orchestration for the complete experiment pipeline.

The pipeline is executed step by step in a fixed order. Each step only starts
after the previous one has finished. This avoids concurrent writes and keeps
the generated artefacts reproducible.
"""

from src.utils.reset_output import reset_pipeline_output
from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.trigger_coverage.runner import run_trigger_coverage_analysis
from src.salting_candidate_selection.runner import run_salting_candidate_selection
from src.salted_email_generator.runner import run_salted_email_generator


def run_full_pipeline() -> None:
    """
    Runs the full experiment pipeline from a clean state.

    Workflow:
    1. Reset all generated output.
    2. Create the train/test split.
    3. Build the trigger vocabularies.
    4. Analyze trigger coverage in test spam emails.
    5. Select salted candidate emails.
    6. Generate salted .eml variants.

    Returns:
        None
    """
    print("=== Full Pipeline Run Started ===")

    reset_pipeline_output()

    print("\n[1/5] Dataset split")
    run_dataset_split()

    print("\n[2/5] Trigger vocabulary construction")
    run_trigger_vocabulary()

    print("\n[3/5] Trigger coverage analysis")
    run_trigger_coverage_analysis()

    print("\n[4/5] Salting candidate selection")
    run_salting_candidate_selection()

    print("\n[5/5] Salted email generation")
    run_salted_email_generator()

    print("\n=== Full Pipeline Run Finished ===")