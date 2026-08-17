# Open Tasks

- [ ] Implement persistence and resumption of Codex threads.
- [ ] Design an equivalent session resumption for Claude.
- [x] Add controlled writes to agents' private memory — done:
      `ALLOWED_MEMORY_TARGETS`/`ContractStore.append_memory()`, wired from
      both `record_architecture_review` and `record_implementation_review`'s
      `memory_updates` handling.
- [ ] Add a `coordinator` profile (`programmer` and `reviewer` already exist).
