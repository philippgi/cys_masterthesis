from src.main_evaluation.analysis.bayes_token_vocab_overlap import run_bayes_token_vocab_overlap
from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.experiments.runner_sa1 import run_sa1
from src.main_evaluation.experiments.runner_sa2 import run_sa2
from src.main_evaluation.experiments.runner_sa3_eval import run_sa3_eval
from src.main_evaluation.experiments.runner_sa3_train import run_sa3_train
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.utils.reset_output import reset_pipeline_output

"""
1 dataset_split
2 trigger_vocabulary
3 trigger_coverage_analysis
4 candidate_selection
5 salted_email_generator
6 spamassassin training
7 spamassassin evaluation
8 Experiments 
    8.1 SpamAssassin 1 (sa1)
    8.2 SpamAssassin 2 (sa2)
    8.3 SpamAssassin 3 (sa3) 
"""


def main():
    # Utils - HANDLE WITH CARE :D

    # ==========================================
    # Utilities
    # ==========================================
    #reset_pipeline_output()

    # ==========================================
    # Manual module execution
    # ==========================================

    # Manual Selection (uses parameter in config.py)
    # Main
    #run_dataset_split()
    #run_trigger_vocabulary()
    #run_trigger_coverage()
    #run_salted_email_generator()
    #run_spamassassin_training()
    #run_spamassassin_evaluation()

    # Analysis
    #run_bayes_token_vocab_overlap()

    # ==========================================
    # Reproducible experiment execution
    # ==========================================

    # Experiments (uses parameter in module)
    #run_sa1()
    run_sa2()
    #run_sa3_train()
    #run_sa3_eval()


if __name__ == "__main__":
    main()