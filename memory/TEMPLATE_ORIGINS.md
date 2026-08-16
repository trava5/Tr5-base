# Template origins

git remote URLs that are point-zero templates, not a real project's
repository. `commit_and_push()` (`agents/git_ops.py`) checks `origin`
against this list before every push and refuses if it still matches one
of these — see ADR-025. Lives in `memory/` since it is long-term project
state, not code (see ADR-027). One URL per line; `#` starts a comment;
blank lines are ignored. Matching ignores a trailing `.git`, a trailing
slash, and case.

After cloning this repository to start a new project, create a fresh,
dedicated repository for it and fill in `GIT_REPO=<new-repo-url>` in
`.env` — `chat_architect.py` redirects `origin` there automatically on
the next run (see ADR-026). This list stays the safety net if that step
is skipped.

https://github.com/mtravnicekarmex/bod_zero.git
https://github.com/mtravnicekarmex/bod-nula.git
https://github.com/trava5/Tr5-base.git
