# Tr5-base agentic workflow

This repository is the next-generation "point zero" project template,
bootstrapped from `bod_zero` (github.com/mtravnicekarmex/bod_zero) and
enriched with mechanisms proven in `Tr5-platform`
(github.com/trava5/Tr5-platform) — see `memory/DECISIONS.md`, ADR-028
onward, for what changed and why. `bod_zero`/`agentCodex` remain their
own lineage (`bod_zero`'s own README explains their relationship);
`Tr5-base` is a separate, deliberate merge of the best of both, not a
periodic snapshot of either. `project/` holds a new project's actual
application code once one is started; `source/` optionally holds the
original/input source of an existing project being migrated onto this
pipeline, kept untouched as a read-only reference (see ADR-024, inherited
from `bod_zero`); the rest of this repository (agents, contracts
pipeline, memory, principles) should otherwise stay untouched, since each
cloned copy lives its own independent life from here on (see ADR-020,
inherited from `bod_zero`, and this repository's own ADR-028).

A thin layer over the Codex SDK and the Claude Agent SDK with a shared
synchronous interface.

The project has two API levels:

- `create_thread(...)` – the low-level technical thread,
- `create_agent("architect", ...)` – a profiled agent with a role, memory,
  and commands.

## Starting a new project from this template

1. Clone this repository into a new directory.
2. Create a new, empty, dedicated git repository for the project.
3. Fill in `GIT_REPO=<new-repo-url>` in `.env`.

`chat_architect.py` redirects `origin` to `GIT_REPO` automatically on
startup (see ADR-026) — no manual `git remote` command needed. Leaving
`GIT_REPO` empty is not a silent bypass: `commit_and_push()`
(`agents/git_ops.py`) separately checks `origin` against
`memory/TEMPLATE_ORIGINS.md` before every push and refuses if it still
points at this template (ADR-025), so a forgotten step 3 blocks the
pipeline's automatic git checkpoints (ADR-019) instead of pushing real
project work back into the template.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Login

```powershell
python -m agents.agent
```

## Profiled agent

```python
from agents.agent import AgentConfig
from agents.agent_profile import create_agent

config = AgentConfig.load()

with create_agent("architect", config=config) as architect:
    print(architect.ask("Review the design of the new layer."))
```

## Talking to the architect

The only entry point at the repository root is `chat_architect.py` — a
single window onto the architect. There is no multi-agent console; the
reviewer and programmer are created internally to run the pipeline, but
you never chat with them directly (see ADR-021).

Run:

```powershell
python chat_architect.py
```

On start, the architect is briefed on the real contract queue and its own
inbox and greets you with that context — e.g. asking what is on the agenda
today — instead of a blind, ungrounded greeting. From there, plain text
goes straight to the architect; the following commands are also available
alongside the conversation:

```text
/new <topic>       architect creates IMPLEMENTATION_CONTRACT_NNNN.md (DRAFT);
                  from there the pipeline runs automatically (architecture
                  review, and if ACCEPTED, implementation and implementation
                  review too, both by the reviewer) and stops once it
                  returns to the architect/owner — unless the contract is
                  high-risk, which pauses twice for /proceed (see below)
/revise <n> <topic> architect rewrites the contract's requirements after
                  CHANGES_REQUESTED from architecture review, resubmits it
                  for review, and continues automatically the same way
/proceed <n>      resumes a high-risk contract paused before implementation
                  or before implementation review; a no-op for
                  standard-risk contracts, which never pause
/work [n]         manual override: programmer picks up contract <n> (or the
                  next ready one) — not needed in the normal flow
/review [n]       manual override: reviewer runs implementation review on
                  contract <n> (or the next ready one) — not needed in the
                  normal flow
/commit <n>       pushes contract <n>'s final `- REVIEWED` checkpoint (must
                  be APPROVED); routine for standard-risk contracts (already
                  auto-pushed, so usually a no-op), the actual manual step
                  for high-risk ones
/status           shows the queue, handoffs, and risk level
/inbox            shows the architect's inbox
/help             shows this list again
/exit             exits
```

### Lifecycle

Three roles, both review gates held by one INDEPENDENT reviewer (Tr5-base
decision 1): the contract is assessed before the programmer ever sees it
(Architecture Review), and again after implementation, against the
Acceptance Criteria of each point plus an explicit Out of Scope check —
did the programmer touch anything beyond what the contract's points call
for (Implementation Review). The architect, who wrote the contract, never
reviews its own proposal or the implementation of it; once implementation
review is complete, the architect (with the owner) looks only at how the
result fits the broader plan and what to do next — a non-gating pass, not
a second approval.

Owner approval happens once, at `/new`/`/revise` — from there a
`standard`-risk contract (the default) runs unattended (architecture
review → programmer → implementation review) and stops again only once it
returns to the architect/owner, whatever the verdict (`APPROVED` or
`CHANGES_REQUESTED`), the same way `ARCHITECTURE_CHANGES_REQUESTED`/
`REJECTED` already stop there today (see ADR-018).

A `high`-risk contract (Tr5-base decisions 7 and 8 — real credentials,
real external calls, native/hardware libraries, or a risk of landing
personal/real data in git) pauses twice instead: right after Architecture
Review is accepted, before the programmer starts, and again right after
the programmer finishes, before the reviewer's Implementation Review
runs — each requiring an explicit `/proceed <n>`. The architect sets
`risk_level` at creation; the reviewer may escalate it to `high` during
Architecture Review, but never lower it back to `standard`.

Three git checkpoints (see ADR-019/ADR-030), auto-pushed regardless of
risk level except the last one: right after architecture review accepts a
contract, the working tree is committed and pushed as `CONTRACT_NNNN` —
the last clean state before implementation starts. Right after the
programmer finishes and self-verifies, before the reviewer's
Implementation Review, it is committed and pushed as
`CONTRACT_NNNN - IMPLEMENTED`. Once Implementation Review approves, it is
committed and pushed as `CONTRACT_NNNN - REVIEWED` — automatically for
`standard`-risk contracts, but for `high`-risk ones this final push is
left to the owner (`/commit <n>`, or the printed git command), not done
by an agent. No commit happens if there is nothing to commit.

```text
architect (create_contract)
  DRAFT → reviewer
                ↓  architecture review
  ACCEPTED → READY_FOR_PROGRAMMER          CHANGES_REQUESTED → ARCHITECTURE_CHANGES_REQUESTED → architect (/revise → back to reviewer)
      ↓                                      REJECTED → REJECTED (end, permanent record) → architect
programmer
  IN_PROGRESS
  READY_FOR_REVIEWER
      ↓  implementation review (reviewer) — per-point + Out of Scope check
reviewer
  APPROVED → owner/architect (non-gating pass)
  CHANGES_REQUESTED → programmer
```

Every contract contains (structure per the Tr5 Document Standard):

- Purpose and Intent — the architectural rationale, kept separate from the
  requirements,
- Current State, Inputs, Outputs, Out of Scope, Future Evolution,
- the requirements and acceptance criteria for every point (Functional
  Requirements),
- the programmer's note for every point, files touched, and tests,
- Architecture Review and Implementation Review as append-only rounds
  (`### Round N`) — review history is never overwritten,
- Completion Notes, Lessons Learned,
- current status and who it is handed off to.

Notifications are written to `agents/<agent>/INBOX.md`. Once approved, a
message is written to `contracts/OWNER_INBOX.md`.

During review the reviewer (architecture review or implementation review)
may propose controlled writes to:

```text
memory/*.md
agents/<agent>/MEMORY.md
agents/<agent>/WORKING_STATE.md
PRINCIPLES.md
```

The host code rejects any other target.

## Permissions

| Profile | Purpose |
| --- | --- |
| `review` | reading and analysis without changing code |
| `edit` | implementation work in the working project |
| `full` | full access including the shell; use sparingly |

The default workflow uses:

- architect: `review`,
- reviewer: `review`,
- programmer: `edit`.

## Roles

Mapping onto the Tr5 Platform Document Standard (Architect / Reviewer /
Implementation Agent; Tr5-base decision 1 gives the reviewer both gates):

| Agent | Tr5 role | Responsibility |
| --- | --- | --- |
| `architect` | Architect | Drafts contracts (Purpose/Intent/points); after implementation review, looks at how the approved result fits the plan (non-gating). |
| `reviewer` | Reviewer | Independently assesses the contract BEFORE implementation (architecture review) and the result AFTER implementation, including an Out of Scope check; the architect never approves its own proposal or its own implementation. |
| `programmer` | Implementation Agent | Implements exclusively what the contract specifies after architecture review `ACCEPTED`. |

## Tests

```powershell
python -m pytest -v
```
