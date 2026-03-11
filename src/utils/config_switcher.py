from pathlib import Path
import shutil
from config import BASE_DIR


LOCAL_CF = BASE_DIR / "configs/spamassassin/local.cf"
EXPERIMENT_DIR = BASE_DIR / "configs/spamassassin/experiments"


def activate_spamassassin_config(config_name: str):

    source = EXPERIMENT_DIR / config_name

    if not source.exists():
        raise FileNotFoundError(f"SpamAssassin config not found: {source}")

    shutil.copy2(source, LOCAL_CF)

    print(f"Activated SpamAssassin config: {config_name}")