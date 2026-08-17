# Tr5-base Discovery Engine

Status: Active

---

## Purpose

The Discovery Engine is responsible for discovering objective facts about
the repository and producing an objective representation of its current
state.

It never performs reasoning.
It never makes decisions.
It never modifies the repository (except its own declared output:
`memory/CURRENT_STATE.md`, and — when asked — snapshot files used for diffing).

Ported from `Tr5-platform`'s own `tools/discovery_engine/` (see ADR-031 in
`memory/DECISIONS.md`), which is where this pattern was proven — this is
one of the mechanisms Tr5-base's bootstrap (ADR-028) was built to carry
forward.

---

## Responsibilities

- Recursively scan the Repository Root.
- Discover directories and files.
- Classify each discovered artifact by type, including this template's
  own governance/agent-memory files as their own category (Tr5-base
  decision 3 — `Agent Memory`, `Agent Working State`, `Agent Role`,
  `Agent Commands`, `Agent Inbox`, `Agent Config`, `Agent Command
  Template`, `Implementation Contract`, `Project Memory`, `Governance
  Document` — not generic "Markdown Document").
- Collect basic metadata for each artifact, including a content hash for
  files.
- Generate `memory/CURRENT_STATE.md`.
- Diff two scans by content hash (`diff_scans`), producing an
  added/removed/changed file list — the mechanism the reviewer's
  Implementation Review Out of Scope check is built on (Tr5-base
  decision 3), so it can mechanically confirm which files changed instead
  of eyeballing a diff.

The Discovery Engine only reports what exists. It never prescribes or
generates repository structure.

---

## Current capabilities (v2.0)

- Recursive repository scan, honoring `.gitignore` (simple, non-negated
  patterns) plus a baseline exclusion of `.git/`.
- Extended artifact classification: `Directory`, `Markdown Document`,
  `Python Source`, `JSON Document`, `YAML Document`, this template's own
  governance/agent-memory categories (see above), `Unknown`.
- Metadata collection per artifact: Name, Relative Path, Artifact Type,
  content hash (files only).
- Deterministic generation of `memory/CURRENT_STATE.md` (no timestamp).
- Snapshot save/load (`save_snapshot`/`load_snapshot`) and diffing
  (`diff_scans`/`render_diff_markdown`) between two scans.

## Wired into the pipeline (Tr5-base decision 3)

- `agents/pipeline.py`'s `create_contract()`/`revise_contract()` run
  `run_discovery_scan()` first, regenerating `memory/CURRENT_STATE.md` before the
  architect drafts a contract's Current State — the "structural trigger"
  that makes PRINCIPLES.md's "discovery precedes reasoning" enforced, not
  just documented.
- `ContractStore.claim()` (the programmer starting work) saves a "before"
  snapshot; `ContractStore.record_programmer_result()` (the programmer
  finishing) saves an "after" snapshot and diffs them. Both live under
  `contracts/.discovery/` (gitignored — disposable working data, not
  permanent history) and the diff is handed to the reviewer as part of
  the Implementation Review command, feeding the Out of Scope check.

---

## Current limitations

Does not:

- parse Markdown or Python content beyond classifying by path/extension,
- inspect Git history,
- validate artifacts,
- detect dependencies,
- perform reasoning,
- use AI.

## Expected evolution

Future capabilities may include Git-aware discovery, content-aware
Markdown/Python discovery, validation, dependency discovery, and
repository metrics — intentionally excluded from v2.0, added only once a
real case justifies them (PRINCIPLES.md P11).
