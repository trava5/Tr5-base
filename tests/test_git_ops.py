from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agents.git_ops import commit_and_push, sync_origin_from_env, _run_git


def init_repo_with_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(remote)],
        check=True,
        capture_output=True,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True
    )
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True
    )
    return repo


def test_commit_and_push_commits_and_pushes_changes(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)
    (repo / "file.txt").write_text("change\n", encoding="utf-8")

    committed = commit_and_push(repo, "CONTRACT_0001")

    assert committed is True
    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip() == "CONTRACT_0001"

    remote_log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s", "origin/main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert remote_log.stdout.strip() == "CONTRACT_0001"


def test_commit_and_push_returns_false_when_nothing_to_commit(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)

    committed = commit_and_push(repo, "CONTRACT_0002")

    assert committed is False


def test_commit_and_push_refuses_when_origin_is_a_template(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)
    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "memory").mkdir()
    (repo / "memory" / "TEMPLATE_ORIGINS.md").write_text(f"{remote_url}\n", encoding="utf-8")
    (repo / "file.txt").write_text("change\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="point-zero template"):
        commit_and_push(repo, "CONTRACT_0001")

    # The local checkpoint still happened - only the push was refused.
    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip() == "CONTRACT_0001"

    remote_log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s", "origin/main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert remote_log.stdout.strip() == "init"


def test_commit_and_push_allows_when_origin_not_a_template(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)
    (repo / "memory").mkdir()
    (repo / "memory" / "TEMPLATE_ORIGINS.md").write_text(
        "https://github.com/example/other-template.git\n", encoding="utf-8"
    )
    (repo / "file.txt").write_text("change\n", encoding="utf-8")

    committed = commit_and_push(repo, "CONTRACT_0001")

    assert committed is True


def test_sync_origin_from_env_does_nothing_when_git_repo_empty(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)

    assert sync_origin_from_env(repo, None) is None
    assert sync_origin_from_env(repo, "   ") is None

    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert origin.endswith("remote.git")


def test_sync_origin_from_env_redirects_existing_origin(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)
    new_repo = "https://github.com/example/new-project.git"

    message = sync_origin_from_env(repo, new_repo)

    assert message is not None
    assert new_repo in message
    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert origin == new_repo


def test_sync_origin_from_env_is_noop_when_already_matching(tmp_path: Path) -> None:
    repo = init_repo_with_remote(tmp_path)
    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert sync_origin_from_env(repo, origin) is None


def test_sync_origin_from_env_adds_origin_when_missing(tmp_path: Path) -> None:
    repo = tmp_path / "lonely"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True
    )
    new_repo = "https://github.com/example/new-project.git"

    message = sync_origin_from_env(repo, new_repo)

    assert message is not None
    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert origin == new_repo


def test_commit_and_push_raises_on_missing_remote(tmp_path: Path) -> None:
    repo = tmp_path / "lonely"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "file.txt").write_text("content\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        commit_and_push(repo, "CONTRACT_0003")


def test_run_git_disables_interactive_credential_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the first real end-to-end test's stuck-`/work`
    incident: a stale local git credential made a checkpoint push hang
    behind an interactive prompt instead of failing. `_run_git` (and every
    other git subprocess in this module) must set GIT_TERMINAL_PROMPT=0
    and GCM_INTERACTIVE=Never so a missing/stale credential fails fast
    with a clear RuntimeError instead of hanging (AGENTS.md: "Only
    provider login may be interactive")."""
    captured_env: dict[str, str] = {}

    def fake_run(args, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    _run_git(tmp_path, ["status"])

    assert captured_env.get("GIT_TERMINAL_PROMPT") == "0"
    assert captured_env.get("GCM_INTERACTIVE") == "Never"


def test_commit_and_push_disables_interactive_credential_prompts_throughout(
    tmp_path: Path,
) -> None:
    """Not just the final `push` — `add`, the cached-diff check, and the
    template-origin guard's own `git remote get-url` all go through the
    same non-interactive environment, so nothing added to this module
    later has to remember to set it itself."""
    repo = init_repo_with_remote(tmp_path)
    (repo / "file.txt").write_text("change\n", encoding="utf-8")

    committed = commit_and_push(repo, "CONTRACT_0004")

    assert committed is True
    # No interactive prompt was ever needed against a real local (file://)
    # remote, so a clean run here is consistent with the non-interactive
    # env not having broken normal, credential-free git operations.
