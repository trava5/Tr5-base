from __future__ import annotations

import os
import subprocess
from pathlib import Path

# AGENTS.md: "Only provider login may be interactive; nothing else should
# require confirmation." A `git push` is not provider login, so it must
# never sit waiting on one either. Left at their defaults, `git` itself
# (GIT_TERMINAL_PROMPT) and Git Credential Manager (GCM_INTERACTIVE) can
# both fall back to an interactive prompt (a terminal prompt, or a GCM
# browser/GUI popup) when the cached credential is stale or missing —
# found the hard way in the first real end-to-end test: a stale local
# credential made a checkpoint push hang indefinitely behind a popup
# window neither `chat_architect.py` nor its own owner necessarily
# noticed, with no error, no timeout, nothing on the console. These two
# env vars force any such prompt to fail immediately instead of hanging,
# so a stale/missing credential surfaces as the same clear, immediate
# `RuntimeError` any other git failure already does (see
# `_run_git`) — fail fast, not fail silent-and-stuck.
_NONINTERACTIVE_GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "Never",
}


def commit_and_push(project_root: Path, message: str) -> bool:
    """Stages everything, commits with `message`, and pushes.

    Returns True if a commit was made, False if there was nothing to
    commit (not an error — the pipeline may call this at a point where the
    working tree is already clean). Raises RuntimeError on any git failure
    (including a failed push), so the caller sees it and does not proceed
    on top of an unsaved state (see PRINCIPLES.md P3).
    """
    _run_git(project_root, ["add", "-A"])

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=project_root,
        env=_non_interactive_env(),
    )
    if diff.returncode == 0:
        return False

    _run_git(project_root, ["commit", "-m", message])
    _refuse_template_origin(project_root)
    _run_git(project_root, ["push"])
    return True


def sync_origin_from_env(project_root: Path, git_repo: str | None) -> str | None:
    """Redirects `origin` at the repository declared in `GIT_REPO` (`.env`).

    Each project's own clone fills in `GIT_REPO` once, after cloning this
    point-zero template — see ADR-026. Called on every startup so filling
    it in is the only manual step; nothing to do if `git_repo` is empty
    (fresh clone, not configured yet — `memory/TEMPLATE_ORIGINS.md`'s push
    guard stays the safety net for that case) or already matches `origin`.
    Returns a human-readable message describing what changed, or None.
    """
    if not git_repo or not git_repo.strip():
        return None
    git_repo = git_repo.strip()

    existing = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=_non_interactive_env(),
    )
    if existing.returncode != 0:
        _run_git(project_root, ["remote", "add", "origin", git_repo])
        return f"origin set to {git_repo} (from GIT_REPO in .env)"

    if _normalize_remote(existing.stdout) == _normalize_remote(git_repo):
        return None

    _run_git(project_root, ["remote", "set-url", "origin", git_repo])
    return f"origin redirected to {git_repo} (was {existing.stdout.strip()}, per GIT_REPO in .env)"


def _refuse_template_origin(project_root: Path) -> None:
    """Blocks the push if `origin` still points at a point-zero template.

    Structural guard, not just a documented step (see PRINCIPLES.md P4) —
    this is the exact mistake that landed real project work on the
    `bod-nula` template repo instead of a dedicated project repo. Silently
    does nothing if `memory/TEMPLATE_ORIGINS.md` or a git remote named
    `origin` is missing, so unrelated setups (including the test suite)
    are unaffected.
    """
    template_file = project_root / "memory" / "TEMPLATE_ORIGINS.md"
    if not template_file.exists():
        return

    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=_non_interactive_env(),
    )
    if origin.returncode != 0:
        return

    templates = {
        _normalize_remote(line)
        for line in template_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    if _normalize_remote(origin.stdout) in templates:
        raise RuntimeError(
            f"Refusing to push: origin ({origin.stdout.strip()}) is still a "
            "point-zero template repository listed in "
            "memory/TEMPLATE_ORIGINS.md. Fill in GIT_REPO in .env with a "
            "new, dedicated repository for this project (or run "
            "`git remote set-url origin <new-repo-url>` directly) before "
            "continuing."
        )


def _normalize_remote(url: str) -> str:
    url = url.strip().lower()
    if url.endswith(".git"):
        url = url[: -len(".git")]
    return url.rstrip("/")


def _run_git(project_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=_non_interactive_env(),
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result


def _non_interactive_env() -> dict[str, str]:
    """The current environment, with `_NONINTERACTIVE_GIT_ENV` layered on
    top. Only `push` (reached through `_run_git`) actually needs a
    credential and can therefore actually prompt; applied uniformly here
    anyway so nothing added to this module later has to remember to."""
    return {**os.environ, **_NONINTERACTIVE_GIT_ENV}
