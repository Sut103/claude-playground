# Repository conventions

Files under `.claude/rules/` are part of the repository clone, so every cloud
session and every collaborator's local session loads them identically. Use them
for standards that must not depend on an individual's machine setup.

## Conventions for this repository

- Development happens on feature branches; do not commit directly to `main`.
- Configuration that must apply to everyone belongs in `.claude/`, never in a
  personal `~/.claude/` directory or in a personal cloud environment.
- Secrets never go into `.claude/settings.json`, cloud environment variables, or
  setup scripts. None of those locations is a secrets store.
