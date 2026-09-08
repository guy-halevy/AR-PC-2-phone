"""Fetch pinned research baselines; never reset existing checkout state."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=None):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "third_party")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "upstream-lock.json").read_text())
    for item in lock["selected_sources"]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", item["name"]):
            raise SystemExit("Invalid checkout name")
        if not re.fullmatch(r"[0-9a-f]{40}", item["commit"]):
            raise SystemExit("An exact commit is required")
        if not re.fullmatch(r"https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", item["url"]):
            raise SystemExit("Expected a public GitHub HTTPS source URL")
        target = args.destination.resolve() / item["name"]
        if not target.exists():
            if args.verify_only:
                raise SystemExit(f"Missing checkout: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            git("clone", "--no-checkout", "--depth", "1", item["url"], str(target))
            git("fetch", "--depth", "1", "origin", item["commit"], cwd=target)
            git("checkout", "--detach", item["commit"], cwd=target)
            if item["recursive_submodules"]:
                git("submodule", "update", "--init", "--recursive", "--depth", "1", cwd=target)
        actual = git("rev-parse", "HEAD", cwd=target)
        if actual != item["commit"]:
            raise SystemExit(f"{target}: revision mismatch; existing checkout left unchanged")
        if git("status", "--porcelain", cwd=target):
            raise SystemExit(f"{target}: worktree changes found; existing checkout left unchanged")
        if item["recursive_submodules"]:
            lines = git("submodule", "status", "--recursive", cwd=target).splitlines()
            # check_output.strip() removes the first leading space only; a
            # leading '-' or '+' still identifies missing/mismatched modules.
            if any(line.startswith(("-", "+", "U")) for line in lines):
                raise SystemExit(f"{target}: missing or mismatched submodule; checkout left unchanged")
        print(f"Verified {item['name']} at {actual}")
    print("Pinned source only. No APK, EXE, or runtime validation was performed.")


if __name__ == "__main__":
    main()
