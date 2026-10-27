# Decision records

Decisions that change how MDOS behaves are recorded here, so that later contributors know what was decided and why.

## Where decisions are recorded today

| Record | Topic |
|---|---|
| [ADR-001 to ADR-008](../04-architecture.md#7-technology-choices-decision-records) | Technology choices: Python and FastAPI, React and Vite, SQLite and PostgreSQL, statistics never computed by a language model, agents propose and people approve, offline-first drafting, hand-built charts, in-process execution |
| [01. Pre-build interview](../01-pre-build-interview.md) | The twelve product questions answered before the build |
| [02. Assumptions register](../02-assumptions-register.md) | The assumptions the build rests on and how each will be validated |
| [18. Interface brief](../18-interface-brief.md) | The Quiet Ledger interface decisions (answers marked Confirm) |
| [19. Security and safety review](../19-security-hardening-review.md) | Security defaults, findings and fixes (answers marked Confirm) |

## Adding a decision

Add a file named `NNNN-short-title.md` (for example `0001-cookie-sessions.md`) with four short sections:
**Context** (the problem and its constraints), **Decision** (what was chosen), **Consequences** (what becomes easier
or harder) and **Status** (proposed, accepted, or replaced by another record). Add it to the table above, and mention
it in `CHANGELOG.md` when users will notice the change.
