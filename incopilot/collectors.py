import subprocess
from typing import List


def _run_cmd(cmd: List[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 and p.stdout.strip() == "":
        raise RuntimeError(p.stderr.strip() or f"Command failed: {' '.join(cmd)}")
    return p.stdout


def from_journal(unit: str, since: str) -> str:
    return _run_cmd(["journalctl", "-u", unit, "--since", since, "--no-pager"])


def from_docker(container: str, since: str) -> str:
    return _run_cmd(["docker", "logs", "--since", since, container])


def from_file(path: str) -> str:
    with open(path, "r", errors="replace") as f:
        return f.read()


def bundle(unit: str, since_journal: str, container: str, since_docker: str) -> str:
    j = from_journal(unit, since_journal)
    d = from_docker(container, since_docker)
    return (
        "=== SOURCE: journalctl ===\n" + j +
        "\n\n=== SOURCE: docker logs ===\n" + d +
        "\n"
    )
