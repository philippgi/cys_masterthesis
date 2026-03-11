from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.trigger_coverage.runner import run_trigger_coverage
from src.salted_email_generator.runner import run_salted_email_generator
from src.utils.reset_output import reset_pipeline_output
from src.spamassassin_training.runner import run_spamassassin_training
from src.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.experiments.runner_sa1 import run_sa1

"""
1 dataset_split
2 trigger_vocabulary
3 trigger_coverage_analysis
4 candidate_selection
5 salted_email_generator
6 spamassassin training
7 spamassassin evaluation
"""


def main():
    # Utils - HANDLE WITH CARE :D
    #reset_pipeline_output()

    # Manual Selection (uses parameter in config.py)
    #run_dataset_split()
    #run_trigger_vocabulary()
    #run_trigger_coverage()
    #run_salted_email_generator()
    #run_spamassassin_training()
    # run_spamassassin_evaluation()

    # Experiments (uses parameter in module)
    run_sa1()


if __name__ == "__main__":
    main()