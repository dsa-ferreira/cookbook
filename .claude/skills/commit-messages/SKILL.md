---
name: commit-messages
description: How to write git commit messages in this repo. Use before every git commit (including commits made during /opsx:apply) and whenever the user asks for a commit message. Produces a Conventional Commits subject plus a short, human-readable body that explains why, not a file list.
---

# Writing commit messages

A commit message is for a human reading `git log` months from now. They can see the diff, so they want to know **what changed in one line, and why, plus anything the diff doesn't make obvious**.

Aim between two failure modes: a one-word message that says nothing, and a padded AI-written essay that nobody reads.

## Format

```
type(scope): imperative summary

Body: why the change was made and the non-obvious decisions in it,
written as plain sentences and wrapped at 72 columns.
```

### Subject line

- Conventional Commits: `type(scope): summary`
  - types: `feat`, `fix`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`
  - scope: the area touched, short and lowercase (`auth`, `config`, `catalog`, `arr`, `docker`, `openspec`). Omit it if nothing fits.
- Imperative mood: "add", "fix", "remove", not "added" / "adds" / "adding".
- At most 72 characters, with no trailing period.
- Be specific: `add bearer token auth with ro/rw scopes`, not `update auth`.

### Body

- Add a body only when the diff doesn't speak for itself. A typo, version bump or formatting change gets the subject only.
- Explain why the change was needed and any decisions a reader might question: trade-offs, a rejected alternative, a non-obvious constraint.
- Write prose. Use bullets only for genuinely separate items (e.g. three unrelated fixes in a cleanup commit).
- Aim for 2-6 lines, with a hard ceiling of about 10. If you need more, the commit probably does too much, so consider splitting it.
- Separate the body from the subject with a blank line and wrap it at 72 columns.
- Keep any trailers the environment requires (e.g. `Co-Authored-By:`) after the body, separated by a blank line.

## Never write

- File-by-file lists ("Added auth.py", "Updated server.py"), because the diff already shows them.
- "This commit...", "This change...", "In this commit we...".
- Hype and filler words: comprehensive, robust, seamless, enhance, significantly, ensure, leverage, various, improvements.
- Closing summaries ("These changes lay the foundation for...", "Overall, this improves...").
- A body that only restates the subject.
- "Added tests", unless the tests are the point of the commit. Tests are expected.

## Example

Too short:

```
auth
```

Padded and unreadable:

```
feat: Implement comprehensive authentication and authorization system

This commit introduces a robust, secure authentication layer for the
mcparr MCP server, ensuring that only authorized clients can access
the system's powerful media management capabilities.

Key changes:
- Added auth.py with BearerAuthMiddleware class
- Implemented constant-time token comparison for enhanced security
- Added comprehensive test coverage in tests/test_auth.py
- Updated server.py to integrate the new middleware
- Added audit logging functionality
- Ensured tokens are never logged

These changes significantly improve the security posture of the
application and lay the foundation for future enhancements.
```

Good:

```
feat(auth): add bearer token auth with ro/rw scopes

Every /mcp request needs a configured client token; missing, empty
and unknown tokens get distinct 401s so misconfigured clients are
easy to diagnose. Read-only clients don't see write tools in the
tool list and are refused if they call one anyway: the call-time
check is the real guard, the filtered list just stops the model
from trying.

Write calls are logged with client name and target, never tokens.
```

## More good examples

Subject only, because the diff is self-explanatory:

```
docs(readme): fix Open WebUI menu path
```

A fix that explains the cause:

```
fix(catalog): match series by tvdb id, not title

find_media marked "The Office (US)" as in-library when only the UK
series was present, because library entries were matched by title.
Lookup and library results are now merged on tvdb_id/tmdb_id.
```

Build change with the reason a reader would ask about:

```
build(docker): run as non-root and add /healthz healthcheck

The stack repo's compose file relies on the container health status
to order startup, so the image needs a HEALTHCHECK that doesn't
depend on Sonarr/Radarr being up.
```

## Before committing

1. Read the staged diff (`git diff --cached`). Write the message from what is actually staged, not from memory of the task.
2. If the staged changes contain unrelated work, split them into separate commits.
3. Check the subject length (72 characters at most) and remove every banned phrase.
4. Pass multi-line messages with a heredoc so the formatting survives:

```bash
git commit -F - <<'EOF'
feat(auth): add bearer token auth with ro/rw scopes

Body text here.
EOF
```
