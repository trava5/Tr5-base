# Source

## Purpose

Holds the original/input source code of an existing project being migrated
onto this agentic pipeline — copied in as-is and kept untouched, a
read-only reference for the architect and programmer to read while drafting
and implementing contracts. New or migrated code is never written here; it
lands in `project/` instead.

## Current capabilities (v0.1)

- Directory exists. Empty until an existing project's source is copied in.

## Current limitations

- "Untouched" is a convention documented in `AGENTS.md`, not enforced by
  tooling — the same way the framework layer at the repository root is
  documented as off-limits rather than sandboxed.

## Planned evolution

- Populated once migration of a specific existing project starts. Internal
  structure mirrors whatever that project already uses.
