# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Master's thesis research project investigating spam filter evasion via **Unicode zero-width character salting**. The pipeline statistically identifies spam-indicative trigger words and inserts invisible Unicode characters to evade SpamAssassin/Rspamd detection.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full experiment pipeline
python main.py

# Start/stop Docker services (SpamAssassin, Rspamd, Redis, Postfix, Unbound)
docker-compose up -d
docker-compose down
docker-compose logs -f
```

There are no automated tests. Pipeline steps can be selectively run by uncommenting/commenting function calls in `main.py`.

## Pipeline Architecture

The pipeline is sequential — each step produces output consumed by the next:

1. **Dataset Split** (`src/dataset_split/`) — 80/20 train/test split of SpamAssassin corpus
2. **Trigger Vocabulary** (`src/trigger_vocabulary/`) — log-odds scoring of tokens to identify spam-indicative words; produces `strict` (score ≥ 3.0) and `extended` (score ≥ 2.5) vocabularies
3. **Trigger Coverage** (`src/trigger_coverage/`) — per-email analysis of trigger word presence; outputs `salted_candidates.csv`
4. **Salted Email Generator** (`src/salted_email_generator/`) — injects zero-width Unicode chars (U+200B, U+200C, U+200D, U+00AD) into trigger words in spam candidate emails
5. **SpamAssassin Training** (`src/spamassassin_training/`) — prepares training data
6. **SpamAssassin Evaluation** (`src/spamassassin_evaluation/`) — communicates with `spamd` via socket (127.0.0.1:783), collects scores and triggered rules
7. **Experiment Summary** (`src/analysis/`) — computes detection rate metrics, paired baseline vs. salted comparisons

Each step has a `runner.py` as its entry point. The `src/experiments/` directory contains experiment-specific orchestrators (e.g., `runner_sa1.py` for the SA1 experiment).

## Key Configuration

All paths, thresholds, and salting parameters are centralized in `config.py`:

- `TRAIN_RATIO = 0.8`, `RANDOM_SEED = 42`
- `MIN_DF_SPAM = 5`, `ALPHA = 1.0` (Laplace smoothing)
- Salting: 1 insertion in subject, 3 in body, after token index 2
- SpamAssassin: `SPAMD_HOST = "127.0.0.1"`, `SPAMD_PORT = 783`

SpamAssassin rule configs live in `configs/spamassassin/experiments/` and are activated via `src/utils/config_switcher.py`.

## Data Layout

- `data/datasets/spamassassin_corpus/` — raw corpus (not tracked)
- `data/datasets/split/` — train/test split output
- `data/output/` — all pipeline outputs (not tracked)
- `docker/` — runtime state for containers (not tracked)

## Utilities

- `src/utils/reset_output.py` — clears pipeline output for a clean re-run
- `src/utils/container_control.py` — restarts Docker containers
- `src/utils/config_switcher.py` — activates a SpamAssassin config variant
