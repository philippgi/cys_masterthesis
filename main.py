from src.main_evaluation.analysis.bayes_token_vocab_overlap import run_bayes_token_vocab_overlap
from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.experiments.runner_rs1 import run_rs1
from src.main_evaluation.experiments.runner_sa1 import run_sa1
from src.main_evaluation.experiments.runner_sa2 import run_sa2
from src.main_evaluation.experiments.runner_sa3_eval import run_sa3_eval
from src.main_evaluation.experiments.runner_sa3_train import run_sa3_train
from src.main_evaluation.main_evaluation_utils.container_control import restart_rspamd
from src.main_evaluation.main_evaluation_utils.rs_config_switcher import activate_rspamd_config
from src.main_evaluation.salted_email_generator.runner import run_salted_email_generator
from src.main_evaluation.spamassassin_evaluation.runner import run_spamassassin_evaluation
from src.main_evaluation.spamassassin_training.runner import run_spamassassin_training
from src.main_evaluation.trigger_coverage.runner import run_trigger_coverage
from src.main_evaluation.trigger_vocabulary.runner import run_trigger_vocabulary
from src.utils.reset_output import reset_pipeline_output
from src.main_evaluation.rspamd_evaluation.runner import run_rspamd_evaluation
from src.main_evaluation.experiments.runner_rs2_train import run_rs2_train
from src.main_evaluation.experiments.runner_rs2_eval import run_rs2_eval
from src.main_evaluation.experiments.runner_rs3_train import run_rs3_train
from src.main_evaluation.experiments.runner_rs3_eval import run_rs3_eval


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

    # SpamAssassin
    #run_spamassassin_training()
    #run_spamassassin_evaluation()

    # Rspamd
    #activate_rspamd_config("base")
    #restart_rspamd()
    #run_rspamd_evaluation()

    # Analysis
    #run_bayes_token_vocab_overlap()

    # ==========================================
    # Reproducible experiment execution
    # ==========================================

    # Experiments (uses parameter in module)
    #run_sa1()
    #run_sa2()
    #run_sa3_train()
    #run_sa3_eval()
    #run_rs1()
    #run_rs2_train()
    #run_rs2_eval()
    #run_rs3_train()
    run_rs3_eval()


if __name__ == "__main__":
    main()