from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from kigit.git_handler import GitError, GitHandler


@pytest.fixture(autouse=True)
def _skip_if_git_missing():
    if shutil.which("git") is None:
        pytest.skip("git not found in PATH")


def test_is_git_repo_false_on_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as td:
        gh = GitHandler(td)
        assert gh.is_git_repo() is False


def test_init_then_is_git_repo_true() -> None:
    with tempfile.TemporaryDirectory() as td:
        gh = GitHandler(td)
        gh.init()
        assert gh.is_git_repo() is True


def test_commit_requires_message() -> None:
    with tempfile.TemporaryDirectory() as td:
        gh = GitHandler(td)
        gh.init()
        with pytest.raises(GitError):
            gh.commit(" ")
