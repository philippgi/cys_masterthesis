from pathlib import Path

# =============================
# 0) Base Config
# =============================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "data/output"

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

SALTING_VOCABULARY = "strict"       # "strict" or "extended"

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
SALT_BODY_MAX_INSERTIONS = 3        # Max 3 token per body
SALT_INSERT_AFTER_INDEX = 2         # Index for insertion

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
# Config for Spamassassin
# =============================
SPAMASSASSIN_CONTAINER = "masterthesis-spamassassin"
SPAMD_HOST = "127.0.0.1"
SPAMD_PORT = 783
SOCKET_TIMEOUT = 30
