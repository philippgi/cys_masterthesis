import subprocess
from src.utils.console import print_section


def restart_spamassassin():
    subprocess.run(
        ["docker", "compose", "restart", "spamassassin"],
        check=True
    )

    print_section("SpamAssassin restarted.")


def restart_rspamd():
    print_section("Recreating rspamd stack")

    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "redis", "unbound", "rspamd"],
        check=True,
    )

    print_section("Rspamd restarted.")
