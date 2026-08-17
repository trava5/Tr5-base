"""Tr5-base Discovery Engine.

Scans the repository, classifies artifacts, and generates
`memory/CURRENT_STATE.md`. Ported from Tr5-platform's `tools/discovery_engine/`
(see ADR-031 in `memory/DECISIONS.md`), extended for Tr5-base with:

- classification of this template's own governance/agent-memory files
  (`agents/<name>/MEMORY.md`, `WORKING_STATE.md`, ...) as their own
  category instead of generic "Markdown Document" (Tr5-base decision 3),
- a diff mode (`diff_scans`) comparing two scans by content hash, feeding
  the reviewer's Out of Scope check during Implementation Review, so it
  can mechanically confirm which files actually changed instead of
  eyeballing a diff (Tr5-base decision 3).

Like the original, it only reports what exists: it never performs
reasoning, never makes decisions, and never modifies repository content
except its own declared output (`memory/CURRENT_STATE.md`, and — when asked —
snapshot files used for diffing).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

GENERATOR_NAME = "Tr5-base Discovery Engine"
GENERATOR_VERSION = "2.0"
# Lives under memory/, not at repository root — the root's file set is
# deliberately fixed (see AGENTS.md, ADR-027); framework state belongs in
# memory/ instead, the same way TEMPLATE_ORIGINS.md already does.
OUTPUT_RELATIVE_PATH = "memory/CURRENT_STATE.md"

# Always excluded regardless of .gitignore: fundamental VCS internals, not a
# matter of project-specific ignore rules.
BASELINE_EXCLUDED_DIRECTORY_NAMES = {".git"}

# Governance/agent-memory files get their own classification instead of
# falling into generic "Markdown Document"/"JSON Document" (Tr5-base
# decision 3's "extended classification"). Order matters: first match wins.
_GOVERNANCE_FILE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^agents/[^/]+/MEMORY\.md$", "Agent Memory"),
    (r"^agents/[^/]+/WORKING_STATE\.md$", "Agent Working State"),
    (r"^agents/[^/]+/ROLE\.md$", "Agent Role"),
    (r"^agents/[^/]+/COMMANDS\.md$", "Agent Commands"),
    (r"^agents/[^/]+/INBOX\.md$", "Agent Inbox"),
    (r"^agents/[^/]+/config\.json$", "Agent Config"),
    (r"^agents/[^/]+/commands/[^/]+\.md$", "Agent Command Template"),
    (r"^contracts/IMPLEMENTATION_CONTRACT_\d+\.md$", "Implementation Contract"),
    (r"^memory/[^/]+\.md$", "Project Memory"),
    (r"^PRINCIPLES\.md$", "Governance Document"),
    (r"^AGENTS\.md$", "Governance Document"),
)
_GOVERNANCE_FILE_MATCHERS = [
    (re.compile(pattern), label) for pattern, label in _GOVERNANCE_FILE_PATTERNS
]


def _load_gitignore_patterns(repository_root: Path) -> tuple[set[str], set[str]]:
    """Read simple, non-negated .gitignore patterns.

    Supports exact directory names (lines ending in "/") and glob patterns
    for files (e.g. "*.pyc", ".DS_Store"). Negation ("!") and nested
    .gitignore files are not supported, matching the original engine's own
    documented v1.1 scope — not present in this template's .gitignore, so
    not implemented ahead of need (P2).
    """
    gitignore_path = repository_root / ".gitignore"
    directory_patterns: set[str] = set()
    file_patterns: set[str] = set()

    if not gitignore_path.exists():
        return directory_patterns, file_patterns

    for raw_line in gitignore_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if line.endswith("/"):
            directory_patterns.add(line.rstrip("/"))
        else:
            file_patterns.add(line)

    return directory_patterns, file_patterns


def _is_excluded_directory(name: str, gitignore_directory_patterns: set[str]) -> bool:
    if name in BASELINE_EXCLUDED_DIRECTORY_NAMES:
        return True
    return any(
        fnmatch.fnmatch(name, pattern) for pattern in gitignore_directory_patterns
    )


def _is_excluded_file(name: str, gitignore_file_patterns: set[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in gitignore_file_patterns)


def classify_artifact(relative_path: str, *, is_directory: bool) -> str:
    if is_directory:
        return "Directory"

    for matcher, label in _GOVERNANCE_FILE_MATCHERS:
        if matcher.match(relative_path):
            return label

    suffix = Path(relative_path).suffix.lower()
    if suffix == ".md":
        return "Markdown Document"
    if suffix == ".py":
        return "Python Source"
    if suffix == ".json":
        return "JSON Document"
    if suffix in (".yaml", ".yml"):
        return "YAML Document"
    return "Unknown"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_repository(repository_root: Path) -> list[dict[str, Any]]:
    """Recursively scans `repository_root`, returning one dict per
    artifact: `name`, `relative_path`, `type`, and `content_hash` (a
    sha256 of file bytes, `None` for directories — used only by
    `diff_scans`, not shown in the rendered Markdown)."""
    repository_root = Path(repository_root).resolve()
    artifacts: list[dict[str, Any]] = []
    directory_patterns, file_patterns = _load_gitignore_patterns(repository_root)

    for dirpath, dirnames, filenames in os.walk(repository_root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not _is_excluded_directory(name, directory_patterns)
        )
        current_dir = Path(dirpath)

        visible_filenames = sorted(
            name for name in filenames if not _is_excluded_file(name, file_patterns)
        )

        for name in dirnames:
            full_path = current_dir / name
            relative_path = full_path.relative_to(repository_root).as_posix()
            artifacts.append(
                {
                    "name": name,
                    "relative_path": relative_path,
                    "type": classify_artifact(relative_path, is_directory=True),
                    "content_hash": None,
                }
            )

        for name in visible_filenames:
            full_path = current_dir / name
            relative_path = full_path.relative_to(repository_root).as_posix()
            artifacts.append(
                {
                    "name": name,
                    "relative_path": relative_path,
                    "type": classify_artifact(relative_path, is_directory=False),
                    "content_hash": _hash_file(full_path),
                }
            )

    artifacts.sort(key=lambda artifact: artifact["relative_path"])
    return artifacts


def _build_tree(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for artifact in artifacts:
        parts = artifact["relative_path"].split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault(parts[-1], {} if artifact["type"] == "Directory" else None)
    return tree


def _render_tree(node: dict[str, Any], prefix: str = "") -> list[str]:
    lines = []
    directories = sorted(name for name, value in node.items() if value is not None)
    files = sorted(name for name, value in node.items() if value is None)

    for name in directories:
        lines.append(f"{prefix}- {name}/")
        lines.extend(_render_tree(node[name], prefix + "  "))
    for name in files:
        lines.append(f"{prefix}- {name}")

    return lines


def render_markdown(artifacts: list[dict[str, Any]]) -> str:
    lines = [
        "# Current State",
        "",
        f"Generator: {GENERATOR_NAME} v{GENERATOR_VERSION}",
        "",
        "Generated automatically before every `create_contract`/"
        "`revise_contract` call — do not edit by hand, edits are "
        "overwritten on the next scan.",
        "",
        "---",
        "",
        "## Repository Structure",
        "",
    ]
    lines.extend(_render_tree(_build_tree(artifacts)))
    lines.extend(
        [
            "",
            "---",
            "",
            "## Artifacts",
            "",
            "| Name | Relative Path | Type |",
            "|---|---|---|",
        ]
    )
    for artifact in artifacts:
        lines.append(
            f"| {artifact['name']} | {artifact['relative_path']} | {artifact['type']} |"
        )
    lines.append("")

    return "\n".join(lines)


def save_current_state(repository_root: Path, content: str) -> Path:
    output_path = Path(repository_root) / OUTPUT_RELATIVE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)
    return output_path


def run_discovery_scan(repository_root: Path) -> Path:
    """Scans `repository_root` and (re)writes `memory/CURRENT_STATE.md`
    there.

    This is the "structural trigger" (Tr5-base decision 3): calling this
    once, automatically, before the architect drafts a contract's Current
    State makes PRINCIPLES.md's "discovery precedes reasoning" rule
    enforced rather than merely documented — the architect reads a file
    that was just regenerated, not one that might be stale.
    """
    artifacts = scan_repository(repository_root)
    content = render_markdown(artifacts)
    return save_current_state(repository_root, content)


def save_snapshot(snapshot_path: Path, artifacts: list[dict[str, Any]]) -> Path:
    """Writes a machine-readable scan for later diffing (`diff_scans`) —
    distinct from `memory/CURRENT_STATE.md`, which is the human-readable
    rendering of a single scan, not something meant to be diffed itself.
    """
    snapshot_path = Path(snapshot_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(artifacts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return snapshot_path


def load_snapshot(snapshot_path: Path) -> list[dict[str, Any]]:
    return json.loads(Path(snapshot_path).read_text(encoding="utf-8"))


def diff_scans(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Compares two scans by `relative_path`, returning added/removed/
    changed file paths. Directories are excluded — only file content
    changes matter for an Out of Scope check. "changed" means the same
    path exists in both scans but its `content_hash` differs.
    """
    before_by_path = {
        a["relative_path"]: a for a in before if a["type"] != "Directory"
    }
    after_by_path = {a["relative_path"]: a for a in after if a["type"] != "Directory"}

    before_paths = set(before_by_path)
    after_paths = set(after_by_path)

    added = sorted(after_paths - before_paths)
    removed = sorted(before_paths - after_paths)
    changed = sorted(
        path
        for path in before_paths & after_paths
        if before_by_path[path]["content_hash"] != after_by_path[path]["content_hash"]
    )
    return {"added": added, "removed": removed, "changed": changed}


def render_diff_markdown(diff: dict[str, list[str]]) -> str:
    """Human-readable rendering of `diff_scans`'s output, for embedding in
    the reviewer's Implementation Review prompt (Tr5-base decision 3) —
    a mechanical Out of Scope check instead of eyeballing `git diff`.
    """
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        return "No files changed since the pre-implementation snapshot."

    lines = []
    for label, key in (("Added", "added"), ("Removed", "removed"), ("Changed", "changed")):
        if diff[key]:
            lines.append(f"{label}:")
            lines.extend(f"- {path}" for path in diff[key])
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) > 1:
        repository_root = Path(sys.argv[1]).resolve()
    else:
        repository_root = Path(__file__).resolve().parents[2]

    run_discovery_scan(repository_root)


if __name__ == "__main__":
    main()
