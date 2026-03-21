from src.main_evaluation.dataset_split.runner import run_dataset_split
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_discovery import run_sa_pilot_bayes_discovery
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_eval import run_sa_pilot_bayes_eval
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_prepare import run_sa_pilot_bayes_prepare
from src.pilot.spamassassin.bayes_based.runner_sa_pilot_bayes_train import run_sa_pilot_bayes_train
from src.pilot.spamassassin.rule_based.runner_sa_pilot_rules import run_sa_pilot_rules
from src.utils.reset_output import reset_pipeline_output


def run_sa_pilot_bayes_discover():
    pass


def main():

    # ==========================================
    # Pilot
    # ==========================================
    ######## Rule-Based
    #run_sa_rule_discovery()
    #run_sa_rule_selection()
    #run_sa_pilot_rules()

    ######## Bayes-Based
    #run_dataset_split()
    #run_sa_pilot_bayes_train()
    #run_sa_pilot_bayes_prepare()
    #run_sa_pilot_bayes_discovery()
    run_sa_pilot_bayes_eval()









    # ==========================================
    # Utilities HANDLE WITH CARE :D
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
    #run_bayes_token_vocab_overlap() # Needs output of run_sa3_train() and run_sa_eval()

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
    #run_rs3_eval()
    #run_rs4_train(0.25)
    #run_rs4_eval(0.25)


if __name__ == "__main__":
    main()