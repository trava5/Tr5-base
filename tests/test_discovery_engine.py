from __future__ import annotations

from pathlib import Path

from tools.discovery_engine.generate_current_state import (
    classify_artifact,
    diff_scans,
    load_snapshot,
    render_diff_markdown,
    render_markdown,
    run_discovery_scan,
    save_snapshot,
    scan_repository,
)


def test_classify_artifact_governance_files() -> None:
    assert classify_artifact("agents/architect/MEMORY.md", is_directory=False) == "Agent Memory"
    assert (
        classify_artifact("agents/architect/WORKING_STATE.md", is_directory=False)
        == "Agent Working State"
    )
    assert classify_artifact("agents/reviewer/ROLE.md", is_directory=False) == "Agent Role"
    assert classify_artifact("agents/programmer/COMMANDS.md", is_directory=False) == "Agent Commands"
    assert classify_artifact("agents/architect/INBOX.md", is_directory=False) == "Agent Inbox"
    assert classify_artifact("agents/reviewer/config.json", is_directory=False) == "Agent Config"
    assert (
        classify_artifact("agents/programmer/commands/implement_contract.md", is_directory=False)
        == "Agent Command Template"
    )
    assert (
        classify_artifact("contracts/IMPLEMENTATION_CONTRACT_0001.md", is_directory=False)
        == "Implementation Contract"
    )
    assert classify_artifact("memory/DECISIONS.md", is_directory=False) == "Project Memory"
    assert classify_artifact("PRINCIPLES.md", is_directory=False) == "Governance Document"
    assert classify_artifact("AGENTS.md", is_directory=False) == "Governance Document"


def test_classify_artifact_generic_and_directory() -> None:
    assert classify_artifact("README.md", is_directory=False) == "Markdown Document"
    assert classify_artifact("agents/pipeline.py", is_directory=False) == "Python Source"
    assert classify_artifact("requirements.txt", is_directory=False) == "Unknown"
    assert classify_artifact("agents", is_directory=True) == "Directory"


def test_scan_repository_finds_files_and_respects_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored/\n*.pyc\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("hello", encoding="utf-8")
    (tmp_path / "skip.pyc").write_text("bytecode", encoding="utf-8")
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    (ignored_dir / "inside.md").write_text("nope", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")

    artifacts = scan_repository(tmp_path)
    relative_paths = {a["relative_path"] for a in artifacts}

    assert "keep.md" in relative_paths
    assert "skip.pyc" not in relative_paths
    assert "ignored" not in relative_paths
    assert "ignored/inside.md" not in relative_paths
    assert not any(p == ".git" or p.startswith(".git/") for p in relative_paths)


def test_scan_repository_excludes_a_directory_ignored_without_a_trailing_slash(
    tmp_path: Path,
) -> None:
    """Regression test: a `.gitignore` entry commonly omits the trailing
    slash for a directory (`.venv`, not `.venv/`) — real git still treats
    a bare name as matching a directory of that name, not files only.
    Found via a real first clone's first `/new` (memory/DECISIONS.md, the
    ADR after ADR-034): a project-local `.venv/` leaked its entire
    vendored package tree into `memory/CURRENT_STATE.md`, because the
    bare `.venv` line was previously tracked only as a file pattern, so
    `os.walk` was never pruned from descending into it."""
    (tmp_path / ".gitignore").write_text(".venv\n", encoding="utf-8")
    venv_site_packages = tmp_path / ".venv" / "lib" / "site-packages"
    venv_site_packages.mkdir(parents=True)
    (venv_site_packages / "somepkg.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "keep.md").write_text("hello", encoding="utf-8")

    artifacts = scan_repository(tmp_path)
    relative_paths = {a["relative_path"] for a in artifacts}

    assert "keep.md" in relative_paths
    assert not any(p == ".venv" or p.startswith(".venv/") for p in relative_paths)


def test_scan_repository_records_content_hash_for_files_not_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.md").write_text("content", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    artifacts = scan_repository(tmp_path)
    by_path = {a["relative_path"]: a for a in artifacts}

    assert by_path["a.md"]["content_hash"] is not None
    assert by_path["sub"]["content_hash"] is None


def test_render_markdown_includes_structure_and_table(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    artifacts = scan_repository(tmp_path)

    content = render_markdown(artifacts)

    assert "# Current State" in content
    assert "## Repository Structure" in content
    assert "## Artifacts" in content
    assert "a.md" in content


def test_run_discovery_scan_writes_current_state_file(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")

    output_path = run_discovery_scan(tmp_path)

    assert output_path == tmp_path / "memory" / "CURRENT_STATE.md"
    assert output_path.is_file()
    assert "a.md" in output_path.read_text(encoding="utf-8")


def test_save_and_load_snapshot_round_trips(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    artifacts = scan_repository(tmp_path)

    snapshot_path = tmp_path / "snapshot.json"
    save_snapshot(snapshot_path, artifacts)
    loaded = load_snapshot(snapshot_path)

    assert loaded == artifacts


def test_diff_scans_detects_added_removed_and_changed_files(tmp_path: Path) -> None:
    (tmp_path / "unchanged.md").write_text("same", encoding="utf-8")
    (tmp_path / "to_remove.md").write_text("bye", encoding="utf-8")
    (tmp_path / "to_change.md").write_text("before", encoding="utf-8")
    before = scan_repository(tmp_path)

    (tmp_path / "to_remove.md").unlink()
    (tmp_path / "to_change.md").write_text("after", encoding="utf-8")
    (tmp_path / "new_file.md").write_text("new", encoding="utf-8")
    after = scan_repository(tmp_path)

    diff = diff_scans(before, after)

    assert diff["added"] == ["new_file.md"]
    assert diff["removed"] == ["to_remove.md"]
    assert diff["changed"] == ["to_change.md"]


def test_diff_scans_excludes_directories() -> None:
    before = [{"relative_path": "sub", "type": "Directory", "content_hash": None}]
    after = [
        {"relative_path": "sub", "type": "Directory", "content_hash": None},
        {"relative_path": "sub/new.md", "type": "Markdown Document", "content_hash": "abc"},
    ]

    diff = diff_scans(before, after)

    assert diff["added"] == ["sub/new.md"]
    assert diff["removed"] == []
    assert diff["changed"] == []


def test_render_diff_markdown_reports_no_changes() -> None:
    diff = {"added": [], "removed": [], "changed": []}
    assert "No files changed" in render_diff_markdown(diff)


def test_render_diff_markdown_lists_each_category() -> None:
    diff = {"added": ["a.py"], "removed": ["b.py"], "changed": ["c.py"]}
    rendered = render_diff_markdown(diff)
    assert "Added:" in rendered and "a.py" in rendered
    assert "Removed:" in rendered and "b.py" in rendered
    assert "Changed:" in rendered and "c.py" in rendered
