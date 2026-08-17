# Reviewer's Commands

You hold both review gates (Tr5-base decision 1) — always on a fresh
thread with no memory of prior contracts (Tr5-base decision 9).

- `architecture_review` — assesses a contract (in status DRAFT) against
  `AGENTS.md` and `memory/DECISIONS.md`, BEFORE implementation. Returns
  verdict `ACCEPTED`, `CHANGES_REQUESTED`, or `REJECTED`; may also
  set/escalate `risk_level` to `high`.
- `review_contract` — implementation review AFTER implementation; checks
  every point against its acceptance criteria, runs the Out of Scope
  check, and proposes memory entries.
