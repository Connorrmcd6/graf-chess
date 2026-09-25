import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Replace the local chess database with a backup")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("This replaces current chess data. Supply --confirm after checking the backup path.")
    with args.backup.open("rb") as file:
        compose("stop", "collector", "grafana")
        compose("up", "-d", "--wait", "db")
        compose("exec", "-T", "db", "pg_restore", "-U", "chess_owner", "-d", "chess",
                "--clean", "--if-exists", "--no-owner", "--exit-on-error", stdin=file)
    compose("up", "-d")
    print("Restored database and restarted the stack")


if __name__ == "__main__":
    main()
