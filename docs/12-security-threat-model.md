# 12 · Security Threat Model

Scope: the MDOS web app in both deployment modes (desktop "local" mode and multi-tenant "cloud" mode), its API,
file handling, agents and the optional Claude integration. Method: assets, trust boundaries, then STRIDE threats with
the control that exists today, how it is verified, and what remains open.

## 1. Assets

| Asset | Why it matters |
|---|---|
| Uploaded datasets (survey answers, reviews) | May contain personal data of respondents; commercially sensitive |
| Research outputs (evidence, insights, reports, decisions) | Drive business decisions; integrity matters as much as confidentiality |
| Accounts and sessions | Access to an organization's projects |
| `SECRET_KEY` (JWT signing), `ANTHROPIC_API_KEY` | Forged sessions; API spend and data exposure |
| Audit log | Accountability for approvals and changes |

## 2. Trust boundaries

1. **Browser to API.** Everything from the browser is untrusted input. In cloud mode it crosses the internet (TLS at
   the load balancer or reverse proxy).
2. **API to database and file storage.** Trusted, but queries must be scoped to the caller's organization and project.
3. **API to Claude.** Outbound; prompts may include customer text (reviews, open answers), so model output is untrusted.
4. **Local mode.** A passwordless single-user session that must only be reachable from the same computer.

## 3. Threats and controls

| # | Threat (STRIDE) | Control in place | Verified by | Open items |
|---|---|---|---|---|
| T1 | Spoofing: stolen or guessed passwords | Argon2id hashing; minimum 10 characters; login rate limit (10 per minute per client); generic error messages | `test_auth_tenancy.py` | No MFA or SSO yet (Phase 2); no account lockout beyond the rate limit |
| T2 | Spoofing: forged tokens | HS256 JWT signed with `SECRET_KEY`; cloud mode refuses to start without a key of 32+ characters; tokens expire (12 hours by default) | Tests for invalid, expired and forged tokens | No token revocation list; logout is client-side |
| T3 | Spoofing: another website driving the passwordless local session (DNS rebinding) | Local mode binds to 127.0.0.1 only and rejects any Host header other than localhost or 127.0.0.1 | `test_security_headers_and_cloud_allowed_hosts` | None known |
| T4 | Elevation: reading or changing another organization's project | Every project route resolves the project through membership (`project_access`) and every child entity through `get_owned(..., project_id)`; roles owner, editor, viewer; writes need editor | Cross-tenant tests return 404; verified again on PostgreSQL in the Docker image | Keep new routes on the same helpers (see AGENTS.md checklist) |
| T5 | Tampering: SQL injection | SQLAlchemy ORM with bound parameters only; no raw SQL built from input | Code review rule | None |
| T6 | Tampering: malicious upload (zip bombs, XML attacks, huge files) | 25 MB upload limit; row and column limits (100,000 by 500); XLSX parsed with `defusedxml` protections; uploads stored under generated keys, never user file names | Upload tests | Virus scanning is out of scope (files are parsed, never executed) |
| T7 | Tampering: spreadsheet formula injection in exports | Exported text cells beginning with `=`, `+`, `-`, `@` are neutralized | Questionnaire export tests | Apply the same helper to any new export |
| T8 | Tampering: cross-site scripting | React escapes all rendered text; report HTML export escapes every value (`html.escape`); CSP forbids framing, plugins and base-URI changes | Code review | A full script-src CSP is not yet set because the report preview writes HTML into a new window |
| T9 | Tampering: prompt injection through reviews or open answers | Customer text is wrapped as untrusted data; agents can only call their allowlisted tools; the model never computes numbers, and drafted text is checked against the computed values (numeric grounding); causal wording is blocked without experimental evidence; everything the model drafts is labeled and needs human approval | `test_agents.py` with a fake adversarial provider | Continue red-teaming prompts as agent features grow |
| T10 | Repudiation: "I did not approve that" | Append-only audit log of every mutation with actor (person or agent), action and entity; approvals record who decided and when, with a rationale | Audit tests | Audit log export and retention settings (Phase 2) |
| T11 | Information disclosure: personal data in datasets | Personal data detection (emails, Indonesian phone numbers, name-like columns) flagged as high severity; pseudonymization operation in the cleaning plan; synthetic demo data is labeled everywhere | Quality tests | Data retention policy and a data processing agreement template are business tasks |
| T12 | Information disclosure: secrets in the repository or client | `.env` is gitignored; API keys are only read server-side; the UI shows whether Claude is on, never the key | Repository scan in final review | Rotate keys if they are ever pasted into an issue or chat |
| T13 | Information disclosure: verbose errors | Structured error responses without stack traces; server logs keep details | API tests check status codes and error shapes; handler reviewed | None |
| T14 | Denial of service: floods of logins, uploads or agent runs | Sliding-window limits for authentication, uploads and agent workflows; statistics capped by row and column limits; bootstrap resamples capped at 20,000 | Rate limit tests | The limiter is in-memory per process; use a shared store (Redis) or the proxy's limits when running several instances |
| T15 | Clickjacking and MIME sniffing | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` | Header test | HSTS should be set at the TLS proxy |
| T16 | Host header abuse in cloud mode | `ALLOWED_HOSTS` restricts accepted host names | Header test | Set it in production (defaults to any host) |
| T17 | Supply chain | Dependencies pinned by minimum version; lockfile for the frontend; CI runs lint and tests on every push | CI | Add Dependabot or Renovate and a `pip-audit`/`npm audit` job |

## 4. Local (desktop) mode specifics

* Data lives in the user's data folder; the JWT key is generated on first start and stored with owner-only
  permissions.
* The server only listens on 127.0.0.1 and refuses other Host headers, so other devices on the network and
  rebinding attacks cannot reach the passwordless session.
* The desktop executable is not code-signed yet, so Windows SmartScreen and macOS Gatekeeper will warn. Signing
  certificates are a manual step for the owner (see the final summary in the repository README).

## 5. Cloud mode checklist before going live

1. Set a random `SECRET_KEY` (48+ characters) and keep it in the host's secret store.
2. Use PostgreSQL with TLS, daily backups and point-in-time recovery.
3. Terminate TLS at a proxy with HSTS; set `ALLOWED_HOSTS` to the public host name.
4. Turn `ALLOW_REGISTRATION` off after the team has signed up, or put the app behind SSO.
5. Keep `CORS_ORIGINS` empty unless another domain must call the API.
6. Run more than one instance only with a shared rate limit store.
7. Review the privacy notice and consent text in the questionnaire with counsel for Indonesia's personal data
   protection law (UU PDP) before collecting real responses.
