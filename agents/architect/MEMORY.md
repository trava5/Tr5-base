# Long-Term Memory: Architect Agent

## Project purpose

Tr5-base is the "point zero" project template every new project is cloned
from (bootstrapped from `agentCodex`/`bod_zero`, enriched with mechanisms
proven in the Tr5 Platform — see `memory/DECISIONS.md` ADR-028 onward). It
provides a thin synchronous layer over the OpenAI Codex SDK and the
Anthropic Claude Agent SDK, plus a three-role contract pipeline
(architect/reviewer/programmer) that governs how real work gets planned,
implemented, and verified once a clone starts holding a real project.

## Current public API

- `create_thread(provider, model, reasoning, permission_profile, config=...)`
- `create_agent(agent_name, config=..., project_root=...)`
- `ask(text)` / `run_command(command_name, **variables)`
- `close()`
- context manager

## Important principles

- `create_thread()` is the low-level technical layer.
- `create_agent()` loads the role, memory, working state, commands, and
  `PRINCIPLES.md`.
- All agents work over a shared project root.
- Specific models live in `.env`; the agent profile uses the `low`, `mid`,
  `high` levels.
- Short-term memory lives in the active thread. Long-term memory lives in
  Markdown files. Runtime data must not be confused with versioned memory.
- Both review gates (Architecture Review, Implementation Review) are held
  by the `reviewer`, never by me — I draft contracts and, once the
  reviewer's loop is done, look only at strategic fit, not correctness.
- The reviewer and the programmer get a brand-new thread for every single
  call — no memory, no carryover between contracts, none between one
  contract's own two review gates either. I am the only role with
  persistent memory across a session.
- `agents/architect/WORKING_STATE.md` is generated from the live contract
  queue on every state transition — I don't write it, and it is not a
  valid `memory_updates` target for any agent.
- Discovery Engine (`tools/discovery_engine/`) scans the repository before
  I draft a contract's "Current State" — read `memory/CURRENT_STATE.md`
  fresh each time rather than relying on what I already believe is there.
- Every contract carries a `risk_level` (`standard`/`high`) I set at
  creation; I can never lower it back down once escalated, only the
  reviewer's escalation (or a later explicit re-escalation of my own) can
  raise it further.
- `/voice` gives the owner a spoken channel into me, but the underlying
  Gemini connection is speech-to-text/text-to-speech only — my own
  reasoning always happens through my own Codex/Claude thread, never
  through Gemini.

## Current limitations

- Thread persistence and resumption across sessions are not implemented —
  `persistent_thread` is a prepared configuration option, currently unread
  by any code path; continuity across sessions is file-based (this file,
  `WORKING_STATE.md`) instead.
- I use the default `review` permission profile, so I do not change files
  myself.
