#!/usr/bin/env python3

from pathlib import Path
import shutil

from config import BASE_DIR
from src.utils.console import print_section


RSPAMD_BASE_DIR = BASE_DIR / "configs/rspamd/base"
RSPAMD_EXPERIMENTS_DIR = BASE_DIR / "configs/rspamd/experiments"
RSPAMD_ACTIVE_DIR = BASE_DIR / "configs/rspamd/active"


def activate_rspamd_config(config_name: str):
    source = RSPAMD_EXPERIMENTS_DIR / config_name

    if not RSPAMD_BASE_DIR.exists():
        raise FileNotFoundError(f"Rspamd base config directory not found: {RSPAMD_BASE_DIR}")

    if not source.exists():
        raise FileNotFoundError(f"Rspamd experiment config directory not found: {source}")

    if RSPAMD_ACTIVE_DIR.exists():
        shutil.rmtree(RSPAMD_ACTIVE_DIR)

    shutil.copytree(RSPAMD_BASE_DIR, RSPAMD_ACTIVE_DIR)
    shutil.copytree(source, RSPAMD_ACTIVE_DIR, dirs_exist_ok=True)

    print_section(f"Activated Rspamd config: {config_name}")
