# Evaluating the Impact of Zero-Width Unicode Salting on Open-Source Email Filters and the Effectiveness of Adversarial Retraining

This repository contains the implementation accompanying the Master's thesis of the same title. It includes the illustrative email-processing pipeline, the pilot study, the main experimental evaluation of SpamAssassin and Rspamd, the corresponding filter configurations, and the generated analysis framework.

The thesis provides the detailed research design, methodology, evaluation metrics, and interpretation of the results. This README focuses on the structure, execution, and configuration of the implementation.

---

## Repository Structure

The main repository components are:

```text
.
├── main.py
├── config.py
├── requirements.txt
├── docker-compose.yml
│
├── configs/
│   ├── spamassassin/
│   │   └── experiments/
│   └── rspamd/
│       ├── base/
│       └── experiments/
│
├── src/
│   ├── email_pipeline/
│   ├── main_evaluation/
│   │   ├── analysis/
│   │   ├── dataset_split/
│   │   ├── experiments/
│   │   ├── main_evaluation_utils/
│   │   ├── rspamd_evaluation/
│   │   ├── rspamd_training/
│   │   ├── salted_email_generator/
│   │   ├── spamassassin_evaluation/
│   │   ├── spamassassin_training/
│   │   ├── trigger_coverage/
│   │   └── trigger_vocabulary/
│   ├── pilot/
│   │   ├── rspamd/
│   │   └── spamassassin/
│   └── utils/
│
├── data/
│   ├── datasets/
│   └── output/
│
└── docker/
```

The three main implementation areas are:

| Directory | Purpose |
| --- | --- |
| `src/email_pipeline/` | Illustrative RFC 5322/MIME processing pipeline used in the technical background |
| `src/pilot/` | White-box pilot study for SpamAssassin and Rspamd |
| `src/main_evaluation/` | Dataset preparation, salting, filter training, evaluation, analysis, and the SA1–RS4 experiment runners |

The SpamAssassin Public Corpus, generated salted email variants, runtime configurations, logs, and persistent Docker state are not included in version
control. Generated evaluation and analysis artifacts used for the thesis are included under `data/output/`.

---

## Setup

### Python Environment

The framework used for the thesis was executed with Python 3.12.3. The required Python packages are pinned in `requirements.txt`.

Create and activate a virtual environment and install the dependencies:

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

### Docker Environment

SpamAssassin, Rspamd, Redis, and Unbound are deployed through `docker-compose.yml`.

The container images are pinned by tag and SHA-256 digest. The required SpamAssassin and Rspamd configurations are activated automatically by the corresponding experiment and pilot runners.

Ensure that Docker and Docker Compose are installed and that the Docker daemon is running before executing workflows that require the email filters.

### Dataset

The experiments use the following subsets of the SpamAssassin Public Corpus:

```text
easy_ham
easy_ham_2
spam
spam_2
```

The corpus itself is not included in this repository. Place the extracted email files in:

```text
data/datasets/spamassassin_corpus/
├── easy_ham/
├── easy_ham_2/
├── spam/
└── spam_2/
```

The framework generates the required dataset split under:

```text
data/datasets/split/
```

The standard main evaluation uses an 80/20 train/test split with the fixed random seed `42`. SA1 uses the complete dataset because it does not include a learned classifier that requires a separate training set.

---

## Running the Framework

`main.py` is the central entry point for the implementation. It groups the available workflows into the following areas:

```text
Email Pipeline
Pilot SpamAssassin
Pilot Rspamd
Manual Main-Evaluation Modules
Reproducible Experiment Execution
Utilities
```

To execute a workflow, enable the corresponding function call or sequence in `main()` and run:

```bash
python main.py
```

Only the workflow intended for the current run should be enabled. Review the active function calls in `main()` before execution.

The main execution and configuration model is:

| Area | Execution | Primary configuration |
| --- | --- | --- |
| Email pipeline | `run_email_pipeline()` | `EMAIL-PIPELINE` section in `config.py` |
| SpamAssassin pilot | Pilot functions in `main.py` | `PILOT` section in `config.py` and pilot case definitions |
| Rspamd pilot | Pilot functions in `main.py` | `PILOT` section in `config.py` and pilot case definitions |
| Manual main evaluation | Individual processing functions | Defaults in `config.py` |
| SA1–RS4 experiments | Predefined experiment runners | Experiment runner parameters and shared settings from `config.py` |

### Email Pipeline

The illustrative processing pipeline is started with:

```python
run_email_pipeline()
```

Its implementation is located in:

```text
src/email_pipeline/
```

The input email is configured through the `EMAIL-PIPELINE` section of `config.py`.

### Pilot Study

The pilot implementation is organized by filter and detection mechanism:

```text
src/pilot/
├── spamassassin/
│   ├── rule_based/
│   └── bayes_based/
└── rspamd/
    ├── rule_based/
    ├── bayes_based/
    └── neural_based/
```

The corresponding preparation, discovery, training, and evaluation functions are exposed in the pilot sections of `main.py`.

For example, the SpamAssassin rule-based pilot is executed through:

```python
run_sa_rule_discovery()
run_sa_rule_selection()
run_sa_pilot_rules()
```

Pilot-specific runtime parameters are defined in the `PILOT` section of `config.py`. The synthetic pilot cases and their target content are defined in the corresponding `cases.py` modules.

### Main Experimental Evaluation

The main experiments are exposed through predefined runners in `main.py`:

| Experiment | Detection setup | Execution |
| --- | --- | --- |
| SA1 | SpamAssassin, restricted lexical rules | `run_sa1()` |
| SA2 | SpamAssassin, extended local content rules | `run_sa2()` |
| SA3 | SpamAssassin, rules + Bayes | `run_sa3_train()` → `run_sa3_eval()` |
| RS1 | Rspamd, rules only | `run_rs1()` |
| RS2 | Rspamd, rules + Bayes | `run_rs2_train()` → `run_rs2_eval()` |
| RS3 | Rspamd, rules + neural network | `run_rs3_train()` → `run_rs3_eval()` |
| RS4 | Rspamd, rules + adversarially retrained neural network | `run_rs4_train(ratio)` → `run_rs4_eval(ratio)` |

Experiments using Bayesian or neural classifiers are separated into training and evaluation stages. The training stage must be completed before the corresponding evaluation stage.

RS3 and RS4 use the same Rspamd filter configuration. RS4 differs from RS3 only in the composition of the neural-network training data.

For RS4, adversarially retrained models are created with salted-spam training proportions of `0.25` and `0.50`. The `0.00` reference reported in the thesis corresponds to the unretrained RS3 model.

```python
run_rs4_train(0.25)
run_rs4_eval(0.25)

run_rs4_train(0.50)
run_rs4_eval(0.50)
```

The predefined experiment runners are located in:

```text
src/main_evaluation/experiments/
```

They combine the individual processing modules into the experiment workflows used for the thesis.

For reproduction of the reported thesis experiments, the predefined runners should be used without modifying their experiment-specific parameters.

---

## Configuration

The framework separates Python-level parameters from email-filter configurations.

### `config.py`

`config.py` contains shared settings and default parameters and is divided into the following areas:

| Section | Purpose |
| --- | --- |
| `BASE CONFIG` | Repository paths, filter endpoints, container names, dataset paths, train/test ratio, and random seed |
| `EMAIL-PIPELINE` | Input path for the illustrative processing pipeline |
| `PILOT` | Pilot-specific filter settings, code points, salting parameters, and output paths |
| `MAIN EVALUATION` | Trigger-vocabulary, trigger-coverage, salting, and related default parameters |
| `ANALYSIS` | Parameters and paths used by supplementary analysis modules |

The values in `config.py` serve as shared settings or defaults.

The `Manual module execution` section of `main.py` allows individual processing stages to be executed using these defaults.

The predefined SA1–RS4 runners instead pass experiment-specific parameters directly to the underlying modules where required. Explicit runner parameters therefore take precedence over the corresponding defaults in `config.py`.

For example, experiment runners can explicitly define:

```text
trigger-vocabulary scope
salting mode
maximum Subject insertions
maximum body insertions
insertion position
output location
```

Shared settings that are not overridden continue to be taken from `config.py`.

### Filter Configurations

Filter configurations are stored separately from the Python implementation under:

```text
configs/
├── spamassassin/
└── rspamd/
```

#### SpamAssassin

Experiment and pilot configurations are stored in:

```text
configs/spamassassin/experiments/
├── sa1.cf
├── sa2.cf
├── sa3.cf
├── sa_pilot_rules.cf
└── sa_pilot_bayes.cf
```

The selected configuration is activated automatically by copying it to:

```text
configs/spamassassin/local.cf
```

which is mounted into the SpamAssassin container.

#### Rspamd

Rspamd uses a common base configuration and experiment-specific overrides:

```text
configs/rspamd/
├── base/
├── experiments/
│   ├── rs1/
│   ├── rs2/
│   ├── rs3/
│   ├── rs4/
│   ├── rs_pilot_rules/
│   ├── rs_pilot_bayes/
│   └── rs_pilot_neural/
└── active/
```

For each run, the framework constructs the active configuration as:

```text
base/
  +
experiments/<configuration>/
  ↓
active/
```

Experiment-specific files override files with the same name from the base configuration. The resulting `active/` directory is mounted into the Rspamd container.

Configuration activation is performed automatically by the corresponding runners.

---

## Generated Output

Generated artifacts are written below:

```text
data/output/
├── email_pipeline/
├── pilot/
└── experiments/
```

Main experiment results are organized by experiment and trigger-vocabulary scope:

```text
data/output/experiments/
└── <experiment>/
    └── <scope>/
```

The main evaluation uses the `strict`, `extended`, and `broad` trigger-vocabulary scopes.

Depending on the workflow, the generated directories contain intermediate and final artifacts such as:

- trigger vocabularies and coverage results,
- salting candidate selections and salting logs,
- generated salted email variants,
- variant-level and paired filter results,
- rule or symbol loss analyses,
- Bayesian or neural analyses,
- aggregated experiment summaries.

The main aggregated results of an experiment are available as:

```text
summary.json
summary.txt
```

Pilot outputs are stored separately below `data/output/pilot/`, while output of the illustrative processing pipeline is stored below `data/output/email_pipeline/`.

---

### Evaluation Populations

The main evaluation follows a population funnel:

- `C`: spam emails containing at least one trigger word in the selected vocabulary scope,
- `V`: emails from `C` for which at least one salted variant was successfully generated,
- `D`: emails from `V` that were detected as spam in the unsalted baseline.

Bypass and other evasion metrics are calculated on `D`, because an email can
only bypass the filter if it was detected before salting.

---

## Reproducibility

The implementation includes several measures intended to support reproducible execution:

- fixed random seed for randomized operations,
- deterministic dataset preparation,
- pinned Python dependencies,
- Docker images pinned by tag and SHA-256 digest,
- version-controlled filter configurations,
- predefined experiment runners for SA1–RS4,
- explicit training and evaluation stages for learned classifiers,
- automatic activation of experiment-specific filter configurations.

For exact reproduction of the submitted thesis results, use the repository commit or release corresponding to the submitted thesis version.

The repository structure follows the processing stages described in the technical background, methodology, pilot study, and experimental evaluation chapters of the accompanying thesis.

---

## Citation

If you use this repository or the experimental methodology, please cite the accompanying thesis:

> Philipp Gigler, *Evaluating the Impact of Zero-Width Unicode Salting on Open-Source Email Filters and the Effectiveness of Adversarial Retraining*, Master's Thesis, University of Applied Sciences Salzburg, 2026.