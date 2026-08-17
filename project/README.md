# Project

## Purpose

Holds the actual application code for the project this clone of Tr5-base
was set up for — kept separate from the agentic framework/governance layer
that lives at the repository root (`chat_architect.py`, `agents/agent.py`,
`agents/agent_profile.py`, `agents/contract_workflow.py`,
`agents/git_ops.py`, `agents/pipeline.py`, `agents/voice.py`,
`agents/<name>/`, `tools/discovery_engine/`, `templates/voice_module/`,
`memory/`, `contracts/`, `AGENTS.md`, `PRINCIPLES.md`). Every implementation
contract's actual code changes land here. When migrating an existing
project, its original source lives in `source/` (untouched, read-only
reference) — see ADR-024.

## Current capabilities (v0.1)

- Directory exists. No project code yet — this is Tr5-base's own "point
  zero" state, the starting point copied for each new project.

## Current limitations

- Empty until the first contract is implemented against a real project.

## Planned evolution

- Grows as contracts are implemented. Internal structure (e.g. a backend/
  frontend split) is decided when a real project actually needs it, not in
  advance (see `PRINCIPLES.md` P1, P15).
