"""
Central configuration for the thesis implementation and experiments.

The module defines shared paths, service settings, pilot parameters,
main-evaluation defaults, and analysis settings.
"""

from pathlib import Path

# =============================
# BASE CONFIG
# =============================
# Project paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "data/output"

# SpamAssassin
SPAMASSASSIN_CONTAINER = "masterthesis-spamassassin"
SPAMD_HOST = "127.0.0.1"
SPAMD_PORT = 783
SOCKET_TIMEOUT = 30

# Rspamd
RSPAMD_CONTAINER = "masterthesis-rspamd"
RSPAMD_REDIS_CONTAINER = "masterthesis-rspamd-redis"

RSPAMD_TRAIN_HAM_CONTAINER_DIR = "/split/train/ham"
RSPAMD_TRAIN_SPAM_CONTAINER_DIR = "/split/train/spam"

RSPAMD_HOST = "127.0.0.1"
RSPAMD_PORT = 11333
RSPAMD_TIMEOUT = 30

# Dataset
DATASET_ROOT = BASE_DIR / "data/datasets/spamassassin_corpus"
DATASET_SPLIT = BASE_DIR / "data/datasets/split"

TRAIN_RATIO = 0.8                                   # Percentage of Trainset, rest is test-set. 1.0 -> 100% Train and 100% Test
RANDOM_SEED = 42

# =============================
# EMAIL-PIPELINE
# =============================
EML_PATH = BASE_DIR / "src/email_pipeline/test_email.eml"

# =============================
# PILOT
# =============================
# SpamAssassin - Rule-based pilot
PILOT_SA_RULE_OUTPUT_DIR = OUTPUT_ROOT / "pilot/sa/rule_based/rules"
PILOT_SA_RULE_CONFIG_NAME = "sa_pilot_rules.cf"

PILOT_SA_RULE_CODEPOINT_NAME = "U+200B"
PILOT_SA_RULE_CODEPOINT_CHAR = "\u200B"
PILOT_SA_RULE_INSERT_AFTER_INDEX = 1

PILOT_SA_RULE_FROM_ADDR = "pilot@example.test"
PILOT_SA_RULE_TO_ADDR = "victim@example.test"

PILOT_SA_RULE_READY_TIMEOUT_SECONDS = 90
PILOT_SA_RULE_READY_POLL_INTERVAL = 2.0

# SpamAssassin - Bayes pilot
PILOT_SA_BAYES_OUTPUT_DIR = OUTPUT_ROOT / "pilot/sa/bayes_based"
PILOT_SA_BAYES_TRAINING_OUTPUT_DIR = OUTPUT_ROOT / "pilot/sa/bayes_based/training"
PILOT_SA_BAYES_CONFIG_NAME = "sa_pilot_bayes.cf"

PILOT_SA_BAYES_CODEPOINT_NAME = "U+200B"
PILOT_SA_BAYES_CODEPOINT_CHAR = "\u200B"

PILOT_SA_BAYES_SUBJECT_MAX_INSERTIONS = 1      # Max 1 token per subject
PILOT_SA_BAYES_BODY_MAX_INSERTIONS = 10        # Max 10 tokens per body

PILOT_SA_BAYES_SALT_MODE = "fragment"          # "single" or "fragment"
PILOT_SA_BAYES_FRAGMENT_MAX_POSITIONS = 4      # None = fragment across all possible positions
PILOT_SA_BAYES_INSERT_AFTER_INDEX = 2          # Index for insertion in "single" mode

PILOT_SA_BAYES_READY_TIMEOUT_SECONDS = 90
PILOT_SA_BAYES_READY_POLL_INTERVAL = 2.0

# Rspamd - Rule-based pilot
PILOT_RS_RULE_OUTPUT_DIR = OUTPUT_ROOT / "pilot/rspamd/rule_based"
PILOT_RS_RULE_DISCOVERY_OUTPUT_DIR = OUTPUT_ROOT / "pilot/rspamd/rule_based/rule_discovery"
PILOT_RS_RULE_CONFIG_NAME = "rs_pilot_rules"

PILOT_RS_RULE_CODEPOINT_NAME = "U+200B"
PILOT_RS_RULE_CODEPOINT_CHAR = "\u200B"

PILOT_RS_RULE_FROM_ADDR = "pilot@example.test"
PILOT_RS_RULE_TO_ADDR = "victim@example.test"

PILOT_RS_RULE_READY_SLEEP_SECONDS = 5

PILOT_RS_RULE_SUBJECT_MAX_INSERTIONS = 1
PILOT_RS_RULE_BODY_MAX_INSERTIONS = 10

PILOT_RS_RULE_SALT_MODE = "single"
PILOT_RS_RULE_INSERT_AFTER_INDEX = 2

# Rspamd - Bayes pilot
PILOT_RS_BAYES_OUTPUT_DIR = OUTPUT_ROOT / "pilot/rspamd/bayes_based"
PILOT_RS_BAYES_CONFIG_NAME = "rs_pilot_bayes"

PILOT_RS_BAYES_CODEPOINT_NAME = "U+200B"
PILOT_RS_BAYES_CODEPOINT_CHAR = "\u200B"

PILOT_RS_BAYES_FROM_ADDR = "pilot@example.test"
PILOT_RS_BAYES_TO_ADDR = "victim@example.test"

PILOT_RS_BAYES_READY_SLEEP_SECONDS = 5

PILOT_RS_BAYES_SALT_MODE = "fragment"
PILOT_RS_BAYES_SUBJECT_MAX_INSERTIONS = 1
PILOT_RS_BAYES_BODY_MAX_INSERTIONS = 10
PILOT_RS_BAYES_INSERT_AFTER_INDEX = 2

# Rspamd - Neural pilot
PILOT_RS_NEURAL_OUTPUT_DIR = OUTPUT_ROOT / "pilot/rspamd/neural_based"
PILOT_RS_NEURAL_CONFIG_NAME = "rs_pilot_neural"

PILOT_RS_NEURAL_CODEPOINT_NAME = "U+200B"
PILOT_RS_NEURAL_CODEPOINT_CHAR = "\u200B"

PILOT_RS_NEURAL_FROM_ADDR = "pilot@example.test"
PILOT_RS_NEURAL_TO_ADDR = "victim@example.test"

PILOT_RS_NEURAL_READY_SLEEP_SECONDS = 5

PILOT_RS_NEURAL_SUBJECT_MAX_INSERTIONS = 1
PILOT_RS_NEURAL_BODY_MAX_INSERTIONS = 10

PILOT_RS_NEURAL_SALT_MODE = "single"                # "single" or "fragment"
PILOT_RS_NEURAL_INSERT_AFTER_INDEX = 2

# =============================
# MAIN EVALUATION
# =============================
# Trigger vocabulary
MIN_DF_SPAM = 5                                     # Absolute minimum spam document frequency.
MIN_DF_SPAM_PERCENTAGE = 0.01                       # Relative minimum spam document frequency.
ALPHA = 1.0                                         # Additive smoothing for log-odds scoring.

# Trigger coverage and candidate selection
SALTING_VOCABULARY = "strict"                       # "strict", "extended", or "broad"

# Salted email generation - paths
SALTING_SELECTION_DIR = OUTPUT_ROOT / "salting_candidate_selection"
SALTED_EMAIL_OUTPUT_DIR = OUTPUT_ROOT / "salted_email_generator"

SALTED_CANDIDATES_CSV = SALTING_SELECTION_DIR / "salted_candidates.csv"
TEST_SPAM_DIR = DATASET_SPLIT / "test" / "spam"
STRICT_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_strict.json"
EXTENDED_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_extended.json"
BROAD_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_broad.json"

SALTING_LOG_CSV = SALTED_EMAIL_OUTPUT_DIR / "salting_log.csv"
SALTED_EMAILS_DIR = SALTED_EMAIL_OUTPUT_DIR / "salted_emails"

# Salted email generation - code points
SALT_CODEPOINTS = {
    "200B": "\u200B",                              # Zero Width Space
    "200C": "\u200C",                              # Zero Width Non-Joiner
    "200D": "\u200D",                              # Zero Width Joiner
    "00AD": "\u00AD",                              # Soft Hyphen
}

# Salted email generation - defaults
# Experiment runners may override these values.
SALT_SUBJECT_MAX_INSERTIONS = 1                    # Max 1 token per subject
SALT_BODY_MAX_INSERTIONS = 3                       # Max 3 token per body

SALT_MODE = "fragment"                             # "single" or "fragment"
SALT_INSERT_AFTER_INDEX = 2                        # Index for insertion in "single mode"
SALT_FRAGMENT_MAX_POSITIONS = None                 # None = fragment across all possible positions in the token in "fragment mode"

# =============================
# ANALYSIS
# =============================
# Bayes token / trigger vocabulary overlap
ANALYSIS_OUTPUT_DIR = OUTPUT_ROOT / "analysis"

BAYES_TOKEN_VOCAB_DATASET_DIR = DATASET_SPLIT
BAYES_TOKEN_VOCAB_SAMPLE_SIZE = 10
BAYES_TOKEN_VOCAB_THRESHOLD = 0.90

BAYES_STRICT_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "SA3" / "strict" / "trigger_vocabulary" / "trigger_words_strict.json"
BAYES_EXTENDED_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "SA3" / "extended" / "trigger_vocabulary" / "trigger_words_extended.json"
BAYES_BROAD_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "SA3" / "broad" / "trigger_vocabulary" / "trigger_words_broad.json"
