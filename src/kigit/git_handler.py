from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import re


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

    def init(self, default_branch: str = "main") -> None:
        """
        Initializes a repository using `default_branch` when possible.
        This avoids creating `master` by default on fresh projects.
        """
        default_branch = (default_branch or "").strip() or "main"
        try:
            # Git 2.28+: supports `git init -b <name>`
            self._run(["init", "-b", default_branch], cwd=self.project_dir)
        except GitError:
            self._run(["init"], cwd=self.project_dir)
            # Best-effort: rename current branch to default_branch.
            try:
                self._run(["checkout", "-B", default_branch], cwd=self.project_dir)
            except GitError:
                pass
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
        # `rev-parse --abbrev-ref HEAD` returns "HEAD" when detached; avoid using that for operations.
        try:
            res = self._run(["symbolic-ref", "--short", "HEAD"], cwd=self._repo_cwd())
            return res.stdout.strip()
        except GitError:
            res = self._run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self._repo_cwd())
            return res.stdout.strip()

    def has_commits(self) -> bool:
        try:
            self._run(["rev-parse", "--verify", "HEAD"], cwd=self._repo_cwd())
            return True
        except GitError:
            return False

    def remote_default_branch(self, remote_name: str = "origin") -> str:
        """
        Returns the default branch name for the remote, e.g. "main".
        Requires the remote refs to be fetched.
        """
        try:
            res = self._run(["rev-parse", "--abbrev-ref", f"{remote_name}/HEAD"], cwd=self._repo_cwd())
            val = res.stdout.strip()
            if "/" in val:
                return val.split("/", 1)[1]
        except GitError:
            pass
        # Fallback heuristics.
        for candidate in ("main", "master"):
            try:
                self._run(["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_name}/{candidate}"], cwd=self._repo_cwd())
                return candidate
            except GitError:
                continue
        return "main"

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

    def commit_count(self) -> int:
        if not self.has_commits():
            return 0
        try:
            res = self._run(["rev-list", "--count", "HEAD"], cwd=self._repo_cwd())
            return int((res.stdout or "").strip() or "0")
        except Exception:
            return 0

    _MAJOR_TAG_RE = re.compile(r"^V(\d+)\.0$")

    def _list_major_tags(self) -> list[tuple[int, str]]:
        """
        Returns parsed major tags as (major, tag_name) for tags matching V<major>.0.
        """
        try:
            res = self._run(["tag", "--list", "V*.0"], cwd=self._repo_cwd())
            tags = [t.strip() for t in (res.stdout or "").splitlines() if t.strip()]
        except GitError:
            tags = []

        out: list[tuple[int, str]] = []
        for t in tags:
            m = self._MAJOR_TAG_RE.match(t)
            if not m:
                continue
            try:
                out.append((int(m.group(1)), t))
            except Exception:
                continue
        return out

    def latest_major_tag(self) -> Optional[tuple[int, str]]:
        """
        Picks the highest major tag matching V<major>.0.
        """
        tags = self._list_major_tags()
        if not tags:
            return None
        return max(tags, key=lambda x: x[0])

    def commits_since(self, rev: str) -> int:
        if not self.has_commits():
            return 0
        try:
            res = self._run(["rev-list", "--count", f"{rev}..HEAD"], cwd=self._repo_cwd())
            return int((res.stdout or "").strip() or "0")
        except Exception:
            return 0

    def next_revision(self, *, create_tag: bool = False) -> str:
        """
        Revision scheme:
        - Major tags are only: V<k>.0
        - If create_tag=False: V{k}.{n+1}, where n is commits since V<k>.0
        - If create_tag=True:  V{k+1}.0 (major bump tag), minor resets to 0.
        """
        latest = self.latest_major_tag()
        base_major = latest[0] if latest else 0
        base_tag = latest[1] if latest else None

        if create_tag:
            return f"V{base_major + 1}.0"

        if base_tag:
            minor = self.commits_since(base_tag) + 1
        else:
            minor = self.commit_count() + 1
        return f"V{base_major}.{minor}"

    def tag_exists(self, name: str) -> bool:
        name = (name or "").strip()
        if not name:
            return False
        try:
            self._run(["show-ref", "--tags", "--verify", "--quiet", f"refs/tags/{name}"], cwd=self._repo_cwd())
            return True
        except GitError:
            return False

    def create_annotated_tag(self, name: str, message: Optional[str] = None) -> None:
        name = (name or "").strip()
        if not name:
            raise GitError("Tag name is empty")
        if self.tag_exists(name):
            return
        msg = (message or name).strip() or name
        self._run(["tag", "-a", name, "-m", msg], cwd=self._repo_cwd())

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

    def rename_current_branch(self, new_name: str) -> str:
        new_name = (new_name or "").strip()
        if not new_name:
            raise GitError("New branch name is empty")
        # `git branch -M <name>` renames the current branch (or creates it when unborn).
        self._run(["branch", "-M", new_name], cwd=self._repo_cwd())
        return new_name

    def ensure_gitignore(self, template_text: str) -> bool:
        """
        Writes .gitignore if missing, otherwise ensures KiGit ignore entries exist.
        Returns True if created or modified.
        """
        path = Path(self._repo_cwd()) / ".gitignore"
        if not path.exists():
            path.write_text(template_text, encoding="utf-8")
            return True

        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:
            return False

        needed = [".kigit/", ".kigit-backups/"]
        to_add: list[str] = []
        for entry in needed:
            if entry not in existing:
                to_add.append(entry)
        if not to_add:
            return False

        try:
            suffix = ("\n" if not existing.endswith("\n") else "") + "\n".join(to_add) + "\n"
            path.write_text(existing + suffix, encoding="utf-8")
            return True
        except Exception:
            return False

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

    def check_remote(self, remote: str = "origin") -> str:
        """
        Verifies the remote is reachable by listing heads.
        Returns stdout (may be empty for an empty repo).
        """
        res = self._run(["ls-remote", "--heads", remote], cwd=self._repo_cwd())
        return res.stdout

    def has_untracked_files(self) -> bool:
        return bool(self.list_untracked_paths())

    def list_untracked_paths(self) -> list[str]:
        """
        Returns repo-relative untracked paths.

        Uses `git status --porcelain=v1 -z` to avoid quoted paths (e.g. filenames with spaces).
        """
        res = self._run(["status", "--porcelain=v1", "-z"], cwd=self._repo_cwd())
        data = res.stdout or ""
        out: list[str] = []
        for rec in data.split("\x00"):
            if not rec:
                continue
            if rec.startswith("?? "):
                out.append(rec[3:])
        return out

    def backup_paths(self, rel_paths: list[str], backup_dir: str) -> list[str]:
        """
        Moves the given repo-relative paths into backup_dir, preserving structure.
        Returns the list of moved paths.
        """
        moved: list[str] = []
        root = Path(self._repo_cwd())
        bdir = Path(backup_dir).resolve()
        bdir.mkdir(parents=True, exist_ok=True)

        for rel in rel_paths:
            rel = (rel or "").strip()
            if not rel or rel.startswith(".git/") or rel == ".git":
                continue
            # Never back up KiGit generated folders; they can be regenerated.
            if rel == "git-exports" or rel.startswith("git-exports/") or rel.startswith("git-exports\\"):
                continue
            if rel == ".kigit-backups" or rel.startswith(".kigit-backups/") or rel.startswith(".kigit-backups\\"):
                continue
            if rel == ".kigit" or rel.startswith(".kigit/") or rel.startswith(".kigit\\"):
                continue
            src = root / rel
            if not src.exists():
                continue
            # Never move the backup directory into itself.
            try:
                src_resolved = src.resolve()
                bdir_str = str(bdir)
                src_str = str(src_resolved)
                # Skip moving the backup dir itself or its contents.
                if src_resolved == bdir or src_str.startswith(bdir_str + os.sep):
                    continue
                # Also skip moving a directory that CONTAINS the backup directory (parent into child).
                if bdir_str.startswith(src_str + os.sep):
                    continue
            except Exception:
                pass
            dest = bdir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved.append(rel)
        return moved

    def remote_has_branches(self, remote_name: str = "origin") -> bool:
        try:
            self.fetch(remote_name)
        except GitError:
            return False
        # `show-ref` on refs/remotes/origin/*
        try:
            res = self._run(["show-ref", "--heads", "--quiet", f"refs/remotes/{remote_name}"], cwd=self._repo_cwd())
            _ = res
        except GitError:
            # Fallback by listing branches.
            try:
                res2 = self._run(["branch", "-r", "--format=%(refname:short)"], cwd=self._repo_cwd())
                return any(line.strip().startswith(f"{remote_name}/") and line.strip() != f"{remote_name}/HEAD" for line in res2.stdout.splitlines())
            except GitError:
                return False
        return True

    def fetch(self, remote_name: str = "origin") -> str:
        res = self._run(["fetch", "--prune", remote_name], cwd=self._repo_cwd())
        # Best-effort: update origin/HEAD to track remote default branch.
        try:
            self._run(["remote", "set-head", remote_name, "--auto"], cwd=self._repo_cwd())
        except GitError:
            pass
        return res.stdout + res.stderr

    def remote_branches(self, remote_name: str = "origin") -> list[str]:
        res = self._run(["branch", "-r", "--format=%(refname:short)"], cwd=self._repo_cwd())
        out: list[str] = []
        prefix = f"{remote_name}/"
        for line in res.stdout.splitlines():
            name = line.strip()
            if not name.startswith(prefix):
                continue
            if name == f"{remote_name}/HEAD":
                continue
            out.append(name[len(prefix) :])
        return out

    def push(self, remote_name: str = "origin", branch: Optional[str] = None, *, include_tags: bool = False) -> str:
        if not branch:
            branch = self.current_branch()
        args = ["push", "-u"]
        if include_tags:
            # Push annotated tags that are reachable from commits being pushed.
            # This avoids pushing unrelated/local-only tags.
            args.append("--follow-tags")
        args += [remote_name, branch]
        res = self._run(args, cwd=self._repo_cwd())
        return res.stdout + res.stderr

    def pull(self, remote_name: str = "origin", branch: Optional[str] = None) -> str:
        # If repo has no commits yet, we need to bootstrap the working tree from the remote.
        if not self.has_commits():
            out = []
            out.append(self.fetch(remote_name))
            branches = self.remote_branches(remote_name)
            if not branches:
                raise GitError(
                    "Remote has no branches yet. Create the first commit locally and push, or initialize the remote with a README."
                )
            default_branch = branch or self.remote_default_branch(remote_name)
            if default_branch not in branches:
                default_branch = branches[0]
            # Create local branch tracking the remote branch.
            self._run(["checkout", "-B", default_branch, "--track", f"{remote_name}/{default_branch}"], cwd=self._repo_cwd())
            out.append(self._run(["pull"], cwd=self._repo_cwd()).stdout)
            return "\n".join([x for x in out if x]).strip()

        if not branch:
            branch = self.current_branch()
            
        try:
            self._run(["branch", f"--set-upstream-to={remote_name}/{branch}", branch], cwd=self._repo_cwd())
        except GitError:
            pass

        # Normal pull: merge remote branch into local branch
        res = self._run(["pull", remote_name, branch], cwd=self._repo_cwd())
        return res.stdout + res.stderr

    def pull_merge(self, remote_name: str = "origin", branch: Optional[str] = None) -> str:
        """
        Pull allowing merge commits (no ff-only).
        """
        if branch:
            res = self._run(["pull", remote_name, branch], cwd=self._repo_cwd())
        else:
            res = self._run(["pull"], cwd=self._repo_cwd())
        return res.stdout + res.stderr

    def pull_rebase(self, remote_name: str = "origin", branch: Optional[str] = None) -> str:
        """
        Pull using rebase to avoid merge commits.
        """
        if branch:
            res = self._run(["pull", "--rebase", remote_name, branch], cwd=self._repo_cwd())
        else:
            res = self._run(["pull", "--rebase"], cwd=self._repo_cwd())
        return res.stdout + res.stderr
