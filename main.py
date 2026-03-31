from src.email_pipeline.runner_email_pipeline import run_email_pipeline
from src.main_evaluation.analysis.bayes_token_vocab_overlap import run_bayes_token_vocab_overlap
from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.main_evaluation.experiments.runner_rs2_eval import run_rs2_eval
from src.main_evaluation.experiments.runner_rs2_train import run_rs2_train
from src.main_evaluation.experiments.runner_rs3_train import run_rs3_train
from src.main_evaluation.experiments.runner_sa3_eval import run_sa3_eval
from src.main_evaluation.experiments.runner_sa3_train import run_sa3_train
from src.pilot.rspamd.bayes_based.runner_rspamd_pilot_bayes_eval import run_rspamd_pilot_bayes_eval

from src.pilot.rspamd.bayes_based.runner_rspamd_pilot_bayes_prepare import run_rspamd_pilot_bayes_prepare
from src.pilot.rspamd.bayes_based.runner_rspamd_pilot_bayes_train import run_rspamd_pilot_bayes_train
from src.pilot.rspamd.neural_based.runner_rspamd_pilot_neural_eval import run_rspamd_pilot_neural_eval
from src.pilot.rspamd.neural_based.runner_rspamd_pilot_neural_prepare import run_rspamd_pilot_neural_prepare
from src.pilot.rspamd.neural_based.runner_rspamd_pilot_neural_train import run_rspamd_pilot_neural_train
from src.pilot.rspamd.rule_based.rule_discovery import run_rspamd_rule_discovery
from src.pilot.rspamd.rule_based.runner_rspamd_pilot_rules import run_rspamd_pilot_rules
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_discovery import run_sa_pilot_bayes_discovery
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_eval import run_sa_pilot_bayes_eval
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_prepare import run_sa_pilot_bayes_prepare
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_train import run_sa_pilot_bayes_train
from src.pilot.spamassassin.rule_based.rule_discovery import run_sa_rule_discovery
from src.pilot.spamassassin.rule_based.rule_selection import run_sa_rule_selection
from src.pilot.spamassassin.rule_based.runner_sa_pilot_rules import run_sa_pilot_rules
from src.utils.reset_output import reset_pipeline_output


def main():
    # ==========================================
    # Email-Pipeline
    # ==========================================
    # run_email_pipeline()

    # ==========================================
    # Pilot Spamassassin
    # ==========================================
    # ---> Rule-Based
    # run_sa_rule_discovery()
    # run_sa_rule_selection()
    # run_sa_pilot_rules()

    # ---> Bayes-Based
    # run_dataset_split()
    run_sa_pilot_bayes_train()
    # run_sa_pilot_bayes_prepare()
    # run_sa_pilot_bayes_discovery()
    # run_sa_pilot_bayes_eval()

    # ---> Neural-Based
    # run_rspamd_pilot_neural_prepare()
    # run_rspamd_pilot_neural_train()
    # run_rspamd_pilot_neural_eval()

    # ==========================================
    # Pilot Rspamd
    # ==========================================
    # ---> Rule-Based
    # run_rspamd_rule_discovery()
    # run_rspamd_pilot_rules()

    # ---> Bayes-Based
    # run_rspamd_pilot_bayes_train()
    # run_rspamd_pilot_bayes_prepare()
    # run_rspamd_pilot_bayes_eval()

    # ==========================================
    # Experiment - Manual module execution (uses parameter in config.py)
    # ==========================================
    # ---> Main
    # run_dataset_split()
    # run_trigger_vocabulary()
    # run_trigger_coverage()
    # run_salted_email_generator()

    # ---> SpamAssassin
    # run_spamassassin_training()
    # run_spamassassin_evaluation()

    # ---> Rspamd
    # activate_rspamd_config("base")
    # restart_rspamd()
    # run_rspamd_evaluation()

    # ---> Analysis
    # run_bayes_token_vocab_overlap() # Needs output of run_sa3_train() and run_sa_eval()

    # ==========================================
    # Experiment - Reproducible experiment execution (uses parameter in module)
    # ==========================================
    # run_sa1()
    # run_sa2()
    # run_sa3_train()
    # run_sa3_eval()
    # run_rs1()
    # run_rs2_train()
    # run_rs2_eval()
    # run_rs3_train()
    # run_rs3_eval()
    # run_rs4_train(0.25)
    # run_rs4_eval(0.25)

    # ==========================================
    # Utilities HANDLE WITH CARE :D
    # ==========================================
    # reset_pipeline_output()


if __name__ == "__main__":
    main()