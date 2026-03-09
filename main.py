from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.dataset_split.runner import run_dataset_split
from src.trigger_vocabulary.runner import run_trigger_vocabulary
from src.trigger_coverage.runner import run_trigger_coverage_analysis
from src.salting_candidate_selection.runner import run_salting_candidate_selection
from src.salted_email_generator.runner import run_salted_email_generator
from src.utils.reset_output import reset_pipeline_output
from src.utils.full_pipeline import run_full_pipeline


"""
1 dataset_split
2 trigger_vocabulary
3 trigger_coverage_analyzis
4 candidate_selection
5 salted_email_generator   ← hier kommt der switch
6 filter_evaluation
"""


def main():
    # Utils - HANDLE WITH CARE :D
    reset_pipeline_output()
    #run_full_pipeline()

    # Modules
    #run_dataset_split()
    #run_trigger_vocabulary()
    #run_trigger_coverage_analysis()
    #run_salting_candidate_selection()
    #run_salted_email_generator()





if __name__ == "__main__":
    main()