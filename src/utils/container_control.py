import subprocess


def restart_spamassassin():

    subprocess.run(["docker", "compose", "stop", "spamassassin"], check=True)
    subprocess.run(["docker", "compose", "up", "-d", "spamassassin"], check=True)

    print("SpamAssassin restarted.")