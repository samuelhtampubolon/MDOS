## What and why

<!-- One or two sentences: the change and the problem it solves. Link the issue if there is one. -->

## How it was checked

<!-- Commands you ran and what you looked at (screens, sample data). -->

## Checklist

- [ ] Small vertical slice with tests; engine changes are checked against a reference.
- [ ] `make lint`, `make test` and, for interface changes, `make e2e` pass; CI is green.
- [ ] Access checks, audit records and approval gates are in place (AGENTS.md section 5).
- [ ] No causal wording without experimental evidence; generated content is labeled.
- [ ] Models changed: migration added and `alembic check` passes.
- [ ] Interface follows docs/09-design-system.md (no shadows or gradients, status with icon and text, table view for charts, keyboard access).
- [ ] Security rules in SECURITY.md section 5 are followed (no new outbound hosts, delete paths or shell commands without the checks described there).
- [ ] `python scripts/check_secrets.py` passes; no secrets, personal data or real respondent data in the diff.
- [ ] Docs and CHANGELOG updated.
