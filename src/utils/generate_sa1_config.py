"""
Generates the restricted SpamAssassin configuration used for experiment SA1.

Installed SpamAssassin rules are read from the evaluation container. Scored
rules are retained only if they directly match the decoded Subject or message
body; all other scored rules are explicitly neutralized.
"""

import re
import subprocess
from pathlib import Path


OUTPUT_PATH = Path("configs/spamassassin/experiments/sa1.cf")
SPAMASSASSIN_SERVICE = "spamassassin"


RULE_RE = re.compile(
    r"^\s*(header|body|rawbody|uri|full|meta)\s+"
    r"([A-Za-z0-9_]+)\s+"
    r"(.+?)\s*$",
    re.IGNORECASE,
)

SCORE_RE = re.compile(
    r"^\s*score\s+([A-Za-z0-9_]+)\s+",
    re.IGNORECASE,
)


BASE_CONFIG = """\
# Scope: direct lexical body rules and decoded Subject regex rules only

use_bayes 0
bayes_auto_learn 0

skip_rbl_checks 1
dns_available no
use_razor2 0
use_pyzor 0
use_dcc 0

"""


def read_spamassassin_rules() -> str:
    """
    Read SpamAssassin rule files from the evaluation container.

    The experiment-specific local.cf file is excluded to avoid influencing
    generation of the SA1 configuration.

    Returns:
        str: Combined content of the installed SpamAssassin rule files.
    """

    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        SPAMASSASSIN_SERVICE,
        "sh",
        "-c",
        """
        find \
            /usr/share/spamassassin \
            /etc/mail/spamassassin \
            /etc/spamassassin \
            -type f -name '*.cf' \
            ! -name 'local.cf' \
            -exec cat {} + 2>/dev/null
        """,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def parse_rule_definitions(config_text: str) -> dict[str, list[tuple[str, str]]]:
    """
    Parse SpamAssassin rule definitions and index them by rule name.

    Args:
        config_text (str): Combined SpamAssassin configuration text.

    Returns:
        dict[str, list[tuple[str, str]]]: Rule types and expressions grouped by rule name.
    """

    definitions: dict[str, list[tuple[str, str]]] = {}

    for line in config_text.splitlines():
        match = RULE_RE.match(line)

        if not match:
            continue

        rule_type = match.group(1).lower()
        rule_name = match.group(2)
        expression = match.group(3).strip()

        definitions.setdefault(rule_name, []).append(
            (rule_type, expression)
        )

    return definitions


def parse_scored_rules(config_text: str) -> set[str]:
    """
    Extract rules with explicitly defined SpamAssassin scores.

    Internal helper rules beginning with '__' are excluded because they do not
    directly contribute to the cumulative score.

    Args:
        config_text (str): Combined SpamAssassin configuration text.

    Returns:
        set[str]: Names of scored non-internal rules.
    """

    scored_rules: set[str] = set()

    for line in config_text.splitlines():
        match = SCORE_RE.match(line)

        if not match:
            continue

        rule_name = match.group(1)

        if rule_name.startswith("__"):
            continue

        scored_rules.add(rule_name)

    return scored_rules


def is_direct_body_rule(rule_type: str, expression: str) -> bool:
    """
    Determine whether a rule directly matches the decoded message body.

    Args:
        rule_type (str): SpamAssassin rule type.
        expression (str): Rule expression.

    Returns:
        bool: True for direct non-eval body rules.
    """

    if rule_type != "body":
        return False

    return not expression.lower().startswith("eval:")


def is_decoded_subject_regex(rule_type: str, expression: str) -> bool:
    """
    Determine whether a rule directly applies a regex to the decoded Subject.

    Args:
        rule_type (str): SpamAssassin rule type.
        expression (str): Rule expression.

    Returns:
        bool: True for direct Subject regex rules.
    """

    if rule_type != "header":
        return False

    return bool(
        re.match(
            r"^Subject\s+(?:=~|!~)\s+",
            expression,
            re.IGNORECASE,
        )
    )


def is_in_scope(
    definitions: list[tuple[str, str]],
) -> bool:
    """
    Determine whether any definition of a scored rule is within the SA1 scope.

    Args:
        definitions (list[tuple[str, str]]): Rule type and expression pairs.

    Returns:
        bool: True if at least one definition is a direct body or Subject rule.
    """

    for rule_type, expression in definitions:
        if is_direct_body_rule(rule_type, expression):
            return True

        if is_decoded_subject_regex(rule_type, expression):
            return True

    return False


def generate_sa1_config(
    definitions: dict[str, list[tuple[str, str]]],
    scored_rules: set[str],
) -> tuple[str, list[str], list[str]]:
    """
    Generate the restricted SpamAssassin configuration for experiment SA1.

    In-scope rules retain their original scores, while all other scored rules
    are explicitly neutralized.

    Args:
        definitions (dict[str, list[tuple[str, str]]]): Parsed rule definitions.
        scored_rules (set[str]): Rules with explicitly defined scores.

    Returns:
        tuple[str, list[str], list[str]]: Generated configuration, retained rules,
        and disabled rules.
    """

    retained_rules: list[str] = []
    disabled_rules: list[str] = []

    for rule_name in sorted(scored_rules):
        rule_definitions = definitions.get(rule_name, [])

        if rule_definitions and is_in_scope(rule_definitions):
            retained_rules.append(rule_name)
        else:
            disabled_rules.append(rule_name)

    lines = [BASE_CONFIG]

    lines.append("# Non-SA1 rules disabled below\n")

    for rule_name in disabled_rules:
        lines.append(f"score {rule_name} 0\n")

    return "".join(lines), retained_rules, disabled_rules


def main() -> None:
    """
    Generate and write the SA1 configuration from the installed SpamAssassin rules.
    """

    print("Reading SpamAssassin rules from container...")

    config_text = read_spamassassin_rules()

    definitions = parse_rule_definitions(config_text)
    scored_rules = parse_scored_rules(config_text)

    sa1_config, retained, disabled = generate_sa1_config(
        definitions,
        scored_rules,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(sa1_config, encoding="utf-8")

    print()
    print(f"Rule definitions found: {len(definitions)}")
    print(f"Scored rules found:      {len(scored_rules)}")
    print(f"SA1 rules retained:      {len(retained)}")
    print(f"Rules disabled:          {len(disabled)}")
    print()
    print(f"Written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()