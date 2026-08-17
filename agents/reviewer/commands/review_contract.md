Run implementation review on this contract — AFTER implementation, against
the Acceptance Criteria of each point (as opposed to architecture review,
which assesses the contract itself before implementation):

File: {{CONTRACT_PATH}}

Contract content:
<contract>
{{CONTRACT_CONTENT}}
</contract>

Read the actual changed source files and tests. Check every point of the
contract. You are given a fresh thread with no memory of this contract's
architecture review, even though `reviewer` ran that gate too — also read
the `# Architecture Review` section (the rounds and findings) so you check
the implementation against what was actually accepted, not only the
original point text in isolation; if those findings clarified or narrowed
a point, that clarification is part of the requirement.

Also check Out of Scope. The Discovery Engine diffed the repository from
right before the programmer claimed this contract to right after it
handed back (Tr5-base decision 3), excluding the contract file itself:

<discovery_diff>
{{OUT_OF_SCOPE_DIFF}}
</discovery_diff>

Compare this against the contract's points — did the programmer touch
anything beyond what the points call for (extra files, unrelated
refactors, scope creep)? Treat this as a mechanical starting point, not a
substitute for reading the files themselves — a file can appear in
"changed" for a legitimate, in-scope reason (e.g. an import touched by a
required change), so still check content, not just the file list. If no
snapshot was available, say so in "out_of_scope_findings" and check the
actual diff yourself instead (e.g. `git diff`). This is a separate check
from per-point approval; an unexplained out-of-scope change is a defect on
its own even if every point is otherwise done correctly. Return only valid
JSON:

{
  "approved": true,
  "summary": "overall review",
  "reviews": [
    {
      "point": 1,
      "status": "APPROVED",
      "review": "concrete findings and verification"
    }
  ],
  "out_of_scope_ok": true,
  "out_of_scope_findings": "what was checked against the diff and with what result",
  "memory_updates": [
    {
      "path": "memory/DECISIONS.md",
      "text": "a permanent, verified finding"
    },
    {
      "path": "agents/programmer/MEMORY.md",
      "text": "a finding important for the programmer's future work"
    }
  ]
}

Rules:
- a review must exist for every point,
- status is only APPROVED or CHANGES_REQUESTED,
- approved may only be true when every point is APPROVED,
- "out_of_scope_ok" and "out_of_scope_findings" are both required — state
  plainly whether anything beyond the contract's points was touched, and
  what you checked to reach that conclusion; `out_of_scope_ok: false`
  forces CHANGES_REQUESTED even if every point is individually APPROVED,
- memory_updates may be an empty list,
- do not store the whole contract or temporary details in memory.
