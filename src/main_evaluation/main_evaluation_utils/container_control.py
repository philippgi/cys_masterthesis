import subprocess
from src.utils.console import print_section


def restart_spamassassin():

    subprocess.run(
        ["docker", "compose", "restart", "spamassassin"],
        check=True
    )

    print_section("SpamAssassin restarted.")
