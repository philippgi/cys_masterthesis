from pathlib import Path

# =============================
# 0) Base Config
# =============================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "data/output"

# =============================
# Config for Spamassassin
# =============================
SPAMASSASSIN_CONTAINER = "masterthesis-spamassassin"
SPAMD_HOST = "127.0.0.1"
SPAMD_PORT = 783
SOCKET_TIMEOUT = 30

# =============================
# Config for Rspamd
# =============================
RSPAMD_CONTAINER = "masterthesis-rspamd"
RSPAMD_REDIS_CONTAINER = "masterthesis-rspamd-redis"

RSPAMD_TRAIN_HAM_CONTAINER_DIR = "/split/train/ham"
RSPAMD_TRAIN_SPAM_CONTAINER_DIR = "/split/train/spam"

RSPAMD_HOST = "127.0.0.1"
RSPAMD_PORT = 11333
RSPAMD_TIMEOUT = 30

# =============================
# 1) dataset_split
# =============================

DATASET_ROOT = BASE_DIR / "data/datasets/spamassassin_corpus"
DATASET_SPLIT = BASE_DIR / "data/datasets/split"

TRAIN_RATIO = 0.8                   # Percentage of Trainset, rest is test-set. 1.0 -> 100% Train and 100% Test
RANDOM_SEED = 42

# =============================
# Config for trigger_vocabulary
# =============================
MIN_DF_SPAM = 5                     # Minimum spam document-frequency threshold
MIN_DF_SPAM_PERCENTAGE = 0.01       # Minimum spam document-frequency threshold
ALPHA = 1.0

# =============================
# Config for trigger_coverage
# =============================

SALTING_VOCABULARY = "strict"       # "strict" or "extended" or "broad"

# =============================
# Config for salted_email_generator
# =============================

SALTING_SELECTION_DIR = OUTPUT_ROOT / "salting_candidate_selection"
SALTED_EMAIL_OUTPUT_DIR = OUTPUT_ROOT / "salted_email_generator"

# Input
SALTED_CANDIDATES_CSV = SALTING_SELECTION_DIR / "salted_candidates.csv"
TEST_SPAM_DIR = DATASET_SPLIT / "test" / "spam"
STRICT_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_strict.json"
EXTENDED_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_extended.json"
BROAD_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "trigger_vocabulary/trigger_words_broad.json"

# Output
SALTING_LOG_CSV = SALTED_EMAIL_OUTPUT_DIR / "salting_log.csv"
SALTED_EMAILS_DIR = SALTED_EMAIL_OUTPUT_DIR / "salted_emails"

# ZWC & Options
SALT_CODEPOINTS = {
    "200B": "\u200B",   # Zero Width Space
    "200C": "\u200C",   # Zero Width Non-Joiner
    "200D": "\u200D",   # Zero Width Joiner
    "00AD": "\u00AD",   # Soft Hyphen
}

SALT_SUBJECT_MAX_INSERTIONS = 1     # Max 1 token per subject
SALT_BODY_MAX_INSERTIONS = 20       # Max 3 token per body

SALT_MODE = "fragment"              # "single" or "fragment"
SALT_INSERT_AFTER_INDEX = 2         # Index for insertion in "single mode"
SALT_FRAGMENT_MAX_POSITIONS = None  # None = fragment across all possible positions in the token in "fragment mode"

# =============================
# Config for bayes_token_vocab_overlap
# =============================

ANALYSIS_OUTPUT_DIR = OUTPUT_ROOT / "analysis"

BAYES_TOKEN_VOCAB_DATASET_DIR = DATASET_SPLIT
BAYES_TOKEN_VOCAB_SAMPLE_SIZE = 10
BAYES_TOKEN_VOCAB_THRESHOLD = 0.90

BAYES_STRICT_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "SA3" / "strict" / "trigger_vocabulary" / "trigger_words_strict.json"
BAYES_EXTENDED_TRIGGER_WORDS_PATH = OUTPUT_ROOT / "SA3" / "extended" / "trigger_vocabulary" / "trigger_words_extended.json"

# =============================
# Config for pilot bayes-based
# =============================
PILOT_SALT_SUBJECT_MAX_INSERTIONS = 1     # Max 1 token per subject
PILOT_SALT_BODY_MAX_INSERTIONS = 20       # Max 3 token per body

PILOT_SALT_MODE = "fragment"              # "single" or "fragment"
PILOT_SALT_INSERT_AFTER_INDEX = 2         # Index for insertion in "single mode"
PILOT_SALT_FRAGMENT_MAX_POSITIONS = None  # None = fragment across all possible positions in the token in "fragment mode"

# =============================
# Config for email-pipeline
# =============================
EML_PATH = BASE_DIR / "src/email_pipeline/test_email.eml"

