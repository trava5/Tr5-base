# Current Project State

The project provides a shared synchronous API for Codex and Claude threads.
It also includes a higher-level agent layer that loads a profile from
`agents/<name>/` and continues to use the existing `create_thread()` as its
technical foundation.

The framework/governance layer (`agent.py`, `agent_profile.py`,
`contract_workflow.py`, `git_ops.py`, `pipeline.py`, `voice.py`) lives
under the `agents/` package, alongside the per-role profile directories
(`agents/architect/`, `agents/reviewer/`, `agents/programmer/`) and two
sibling top-level directories, `tools/discovery_engine/` and
`templates/voice_module/`. The repository root has exactly one `.py` file,
`chat_architect.py` — a single window onto the architect; the reviewer and
programmer are created internally to run the pipeline (a brand-new thread
per call, never reused — Tr5-base decision 9) but are not chatted with
directly. On start, the architect is briefed with the real contract queue
and its own inbox before its first greeting (see ADR-021).

Since the `Tr5-base` bootstrap (`memory/DECISIONS.md` ADR-028 onward), the
pipeline has grown considerably beyond the `bod_zero`/`agentCodex` starting
point: the `reviewer` holds both review gates, Architecture Review and
Implementation Review, including an explicit Out of Scope check — the
architect never approves its own proposal or its own implementation
(decision 1). Every contract carries a `risk_level` (`standard`/`high`)
that gates whether the pipeline runs straight through or pauses twice for
an explicit `/proceed` (decision 7). Three git checkpoints
(`CONTRACT_NNNN`, `- IMPLEMENTED`, `- REVIEWED`) mark the pipeline's
progress automatically, except the final one for `high`-risk contracts,
which the owner pushes manually (decision 5). `tools/discovery_engine/`
scans the repository before a contract is drafted and again before/after
implementation, feeding the reviewer's Out of Scope check a mechanical
diff instead of a manual `git diff` read (decision 3).
`agents/architect/WORKING_STATE.md` is generated from the live contract
queue, never agent-authored (decision 10). `/voice` in `chat_architect.py`
gives a spoken channel into the architect, using a separate Gemini
connection for speech-to-text/text-to-speech only — never for the
architect's own reasoning (decision 4).
