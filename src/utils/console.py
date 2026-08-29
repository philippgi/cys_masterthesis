#!/usr/bin/env python3
"""
Provides shared console formatting and progress helpers.
"""

from __future__ import annotations

from typing import Mapping, Any

from colorama import Fore, Style, init
from tqdm import tqdm

init(autoreset=True)


def print_step(title: str) -> None:
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== {title} ==={Style.RESET_ALL}\n")


def print_section(title: str) -> None:
    print("\n"f"{Fore.YELLOW}{title}{Style.RESET_ALL}")


def print_kv(key: str, value: Any) -> None:
    print(f"  {key:20s}: {value}")


def print_dict(data: Mapping[str, Any]) -> None:
    """
    Print all key-value pairs in a mapping.

    Args:
        data (Mapping[str, Any]): Mapping to print.
    """

    for key, value in data.items():
        print_kv(key, value)


def print_success(message: str) -> None:
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")


def print_warning(message: str) -> None:
    print(f"{Fore.MAGENTA}WARNING: {message}{Style.RESET_ALL}")


def print_error(message: str) -> None:
    print(f"{Fore.RED}{Style.BRIGHT}ERROR: {message}{Style.RESET_ALL}")


def print_end(title: str):
    print(f"{Fore.CYAN}OK{Style.RESET_ALL}")


def progress(iterable, desc: str, unit: str = "item"):
    """
    Create a configured tqdm progress iterator.

    Args:
        iterable: Iterable to wrap.
        desc (str): Progress bar description.
        unit (str): Unit label shown by tqdm.

    Returns:
        tqdm: Configured progress iterator.
    """

    return tqdm(
        iterable,
        desc=desc,
        unit=unit,
        colour="green",
        leave=True,
    )
