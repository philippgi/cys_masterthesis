from pathlib import Path

# =============================
# Base Config
# =============================

BASE_DIR = Path(__file__).resolve().parent

# =============================
# Config for dataset_split
# =============================

DATASET_ROOT = BASE_DIR / "data/datasets/spamassassin_corpus"
DATASET_SPLIT = BASE_DIR / "data/datasets/split"

TRAIN_RATIO = 0.8
RANDOM_SEED = 42

# =============================
# Config for trigger_vocabulary
# =============================

OUTPUT_DIR = BASE_DIR / "data/output/trigger_vocabulary"
MIN_DF_SPAM = 5                     # Minimum spam document-frequency threshold
MIN_DF_SPAM_PERCENTAGE = 0.01       # Minimum spam document-frequency threshold
ALPHA = 1.0

# =============================
# Config for salting_candidate_selection
# =============================

SALTING_VOCABULARY = "strict"   # "strict" or "extended"

# =============================
# Config for salted_email_generator
# =============================

SALTING_SELECTION_DIR = BASE_DIR / "data/output/salting_candidate_selection"
SALTED_EMAIL_OUTPUT_DIR = BASE_DIR / "data/output/salted_email_generator"

SALTED_CANDIDATES_CSV = SALTING_SELECTION_DIR / "salted_candidates.csv"
SALTING_LOG_CSV = SALTED_EMAIL_OUTPUT_DIR / "salting_log.csv"
SALTED_EMAILS_DIR = SALTED_EMAIL_OUTPUT_DIR / "salted_emails"

STRICT_TRIGGER_WORDS_PATH = OUTPUT_DIR / "trigger_words_strict.json"
EXTENDED_TRIGGER_WORDS_PATH = OUTPUT_DIR / "trigger_words_extended.json"

TEST_SPAM_DIR = DATASET_SPLIT / "test" / "spam"

SALT_CODEPOINTS = {
    "200B": "\u200B",   # Zero Width Space
    "200C": "\u200C",   # Zero Width Non-Joiner
    "200D": "\u200D",   # Zero Width Joiner
    "00AD": "\u00AD",   # Soft Hyphen
}

SALT_SUBJECT_MAX_INSERTIONS = 1
SALT_BODY_MAX_INSERTIONS = 3
SALT_INSERT_AFTER_INDEX = 2


# =============================
# Config for utils
# =============================

OUTPUT_ROOT = BASE_DIR / "data/output"
