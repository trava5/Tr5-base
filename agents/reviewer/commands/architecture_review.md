Run architecture review on this contract — BEFORE implementation, before
the programmer sees it. You did not write this contract; you are assessing
someone else's proposal:

File: {{CONTRACT_PATH}}

Contract content:
<contract>
{{CONTRACT_CONTENT}}
</contract>

Assess the contract itself, not the future implementation. Verify it
against `AGENTS.md` and against `memory/DECISIONS.md`. In particular check:

- does "Purpose"/"Intent" match a real architectural need, or is this a
  premature abstraction (build today's need, not tomorrow's assumption)?
- are the points ("Functional Requirements") actionable in the stated
  order, and does every one have a clearly verifiable acceptance
  criterion?
- is "Out of Scope" explicit about edge cases, or is there a risk the
  programmer will have to guess?
- does the contract violate backward compatibility without an explicit
  justification?
- does the contract require destructive commands or access beyond the
  `programmer` profile (`edit`)?
- is the requirement complete enough to be implemented without further
  questions?
- if the contract proposes a specific new file/directory name, does it
  follow the naming convention in `AGENTS.md` (`lowercase_with_underscores`,
  no diacritics, no hyphens)?

Also check the contract's `risk_level` (Tr5-base decision 7): does it
involve real credentials/API keys, real calls to external systems,
native/hardware libraries, or a risk of landing personal/real data in
git, and the architect marked it `"standard"` anyway? If so, escalate it.

Do not edit files. Return only valid JSON with no additional commentary:

{
  "verdict": "ACCEPTED",
  "findings": "what was verified, against what, and with what result",
  "memory_updates": [
    {
      "path": "memory/DECISIONS.md",
      "text": "a permanent, verified finding worth keeping beyond this contract"
    }
  ]
}

Include `"risk_level": "high"` in the JSON only when escalating — omit
the key entirely otherwise; you may never lower a contract's risk_level
back to `"standard"`.

Rules:
- "verdict" is only `ACCEPTED`, `CHANGES_REQUESTED`, or `REJECTED`,
- `ACCEPTED` means the contract may go to the programmer as written,
- `CHANGES_REQUESTED` means the requirements themselves need to be
  rewritten (the contract goes back to the architect for revision, not to
  the programmer),
- use `REJECTED` only when the request as a whole is architecturally
  wrong and not worth fixing by rewriting the requirements,
- "findings" must be concrete — not "looks good", but what was
  specifically checked and why it held up or did not,
- "memory_updates" is optional and may be an empty list — you do not need
  to remember the discussion itself, only a fact worth keeping beyond this
  one contract (e.g. a recurring risk, a principle that needs revisiting).
  Allowed targets: `memory/*.md`, `agents/<agent>/MEMORY.md`,
  `PRINCIPLES.md`. Do not store the whole contract or temporary details.
