from __future__ import annotations

import argparse
import sys

from .git_handler import GitHandler


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="KiGit dev helper (non-KiCad).")
    parser.add_argument("project_dir", help="Path to a KiCad project directory")
    args = parser.parse_args(argv)

    gh = GitHandler(args.project_dir)
    print(f"project_dir: {gh.project_dir}")
    print(f"is_git_repo: {gh.is_git_repo()}")
    if gh.is_git_repo():
        print(f"repo_root: {gh.repo_root()}")
        print(f"branch: {gh.current_branch()}")
        print("status:")
        print(gh.status_porcelain())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

