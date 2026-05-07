from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


class GitHandler:
    def __init__(self, project_dir: str, git_exe: str = "git", timeout_s: int = 30) -> None:
        self.project_dir = os.path.abspath(project_dir)
        self._git = git_exe
        self._timeout_s = timeout_s
        self._repo_root_cache: Optional[str] = None

    def _run(self, args: Iterable[str], cwd: Optional[str] = None) -> GitResult:
        argv = [self._git, *list(args)]
        run_cwd = cwd or self.project_dir
        try:
            cp = subprocess.run(
                argv,
                cwd=run_cwd,
                text=True,
                capture_output=True,
                timeout=self._timeout_s,
                check=False,
            )
        except FileNotFoundError as e:
            raise GitError("git executable not found. Install Git and ensure `git` is in PATH.") from e
        except subprocess.TimeoutExpired as e:
            raise GitError(f"git command timed out: {' '.join(argv)}") from e

        res = GitResult(
            argv=argv,
            cwd=run_cwd,
            returncode=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )
        if res.returncode != 0:
            msg = res.stderr.strip() or res.stdout.strip() or f"git failed ({res.returncode})"
            raise GitError(msg)
        return res

    def _repo_cwd(self) -> str:
        """
        Prefer running commands at repo root once initialized/discovered.
        Falls back to project_dir when not in a work tree.
        """
        if self._repo_root_cache:
            return self._repo_root_cache
        try:
            root = self._run(["rev-parse", "--show-toplevel"]).stdout.strip()
            if root:
                self._repo_root_cache = root
                return root
        except GitError:
            return self.project_dir
        return self.project_dir

    def is_git_repo(self) -> bool:
        try:
            self._run(["rev-parse", "--is-inside-work-tree"])
            return True
        except GitError:
            return False

    def repo_root(self) -> str:
        return self._repo_cwd()

    def init(self) -> None:
        self._run(["init"], cwd=self.project_dir)
        self._repo_root_cache = self.project_dir

    def status_porcelain(self) -> str:
        res = self._run(["status", "--porcelain=v1"], cwd=self._repo_cwd())
        return res.stdout

    def add_all(self) -> None:
        self._run(["add", "-A"], cwd=self._repo_cwd())

    def commit(self, message: str) -> str:
        message = (message or "").strip()
        if not message:
            raise GitError("Commit message is empty")
        try:
            self._run(["commit", "-m", message], cwd=self._repo_cwd())
        except GitError as e:
            msg = str(e)
            if "nothing to commit" in msg.lower() or "no changes added to commit" in msg.lower():
                return ""
            if "user.name" in msg or "user.email" in msg or "Author identity unknown" in msg:
                raise GitError(
                    "Git author identity is not configured. Set `git config --global user.name` and "
                    "`git config --global user.email` (or configure per-repo)."
                ) from e
            raise
        return self.head_short()

    def head_short(self) -> str:
        res = self._run(["rev-parse", "--short", "HEAD"], cwd=self._repo_cwd())
        return res.stdout.strip()

    def current_branch(self) -> str:
        res = self._run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self._repo_cwd())
        return res.stdout.strip()

    def list_branches(self) -> list[str]:
        res = self._run(["branch", "--format=%(refname:short)"], cwd=self._repo_cwd())
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def log_graph(self, *, max_count: int = 50, all_branches: bool = True) -> str:
        args = ["log", "--graph", "--oneline", "--decorate"]
        if all_branches:
            args.append("--all")
        args += ["-n", str(max_count)]
        res = self._run(args, cwd=self._repo_cwd())
        return res.stdout

    def log_commits_tsv(self, *, max_count: int = 100, all_branches: bool = True) -> str:
        """
        Returns tab-separated rows:
          short_hash \\t iso_date \\t author \\t decorations \\t subject
        """
        fmt = "%h%x09%ad%x09%an%x09%d%x09%s"
        args = ["log", f"--pretty=format:{fmt}", "--date=iso"]
        if all_branches:
            args.append("--all")
        args += ["-n", str(max_count)]
        res = self._run(args, cwd=self._repo_cwd())
        return res.stdout

    def get_commit_count(self) -> int:
        try:
            res = self._run(["rev-list", "--count", "HEAD"], cwd=self._repo_cwd())
            return int(res.stdout.strip())
        except GitError:
            return 0

    def show_summary(self, rev: str) -> str:
        res = self._run(["show", "--no-patch", "--stat", "--decorate", rev], cwd=self._repo_cwd())
        return res.stdout

    def diff_range(self, rev_a: str, rev_b: str) -> str:
        res = self._run(["diff", f"{rev_a}..{rev_b}"], cwd=self._repo_cwd())
        return res.stdout

    def diff_to_parent(self, rev: str) -> str:
        # Handles merge commits too; keeps it simple for now.
        return self.diff_range(f"{rev}^", rev)

    def create_branch(self, name: str, checkout: bool = False) -> None:
        name = (name or "").strip()
        if not name:
            raise GitError("Branch name is empty")
        self._run(["branch", name], cwd=self._repo_cwd())
        if checkout:
            self.checkout(name)

    def checkout(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            raise GitError("Branch name is empty")
        self._run(["checkout", name], cwd=self._repo_cwd())

    def ensure_gitignore(self, template_text: str) -> bool:
        """
        Writes .gitignore if missing. Returns True if created.
        """
        path = Path(self._repo_cwd()) / ".gitignore"
        if path.exists():
            return False
        path.write_text(template_text, encoding="utf-8")
        return True

    def get_remote_url(self, remote_name: str = "origin") -> str:
        try:
            res = self._run(["remote", "get-url", remote_name], cwd=self._repo_cwd())
            return res.stdout.strip()
        except GitError:
            return ""

    def set_remote_url(self, url: str, remote_name: str = "origin") -> None:
        url = url.strip()
        if not url:
            raise GitError("Remote URL cannot be empty")
        # Check if remote exists
        try:
            self._run(["remote", "get-url", remote_name], cwd=self._repo_cwd())
            remote_exists = True
        except GitError:
            remote_exists = False

        if remote_exists:
            self._run(["remote", "set-url", remote_name, url], cwd=self._repo_cwd())
        else:
            self._run(["remote", "add", remote_name, url], cwd=self._repo_cwd())

    def push(self, remote_name: str = "origin", branch: Optional[str] = None, *, include_tags: bool = False) -> str:
        if not branch:
            branch = self.current_branch()
        args = ["push"]
        if include_tags:
            # Note: plain `git push origin <branch>` does NOT push tags.
            # `--tags` pushes lightweight + annotated tags.
            args.append("--tags")
        args += [remote_name, branch]
        res = self._run(args, cwd=self._repo_cwd())
        return res.stdout + res.stderr

    def pull(self, remote_name: str = "origin", branch: Optional[str] = None) -> str:
        if not branch:
            branch = self.current_branch()
        res = self._run(["pull", remote_name, branch], cwd=self._repo_cwd())
        return res.stdout + res.stderr

    def tag(self, tag_name: str, message: str = "") -> None:
        tag_name = tag_name.strip()
        if not tag_name:
            raise GitError("Tag name cannot be empty")
        args = ["tag", tag_name]
        if message:
            # Message implies an annotated tag.
            args = ["tag", "-a", tag_name, "-m", message]
        self._run(args, cwd=self._repo_cwd())
