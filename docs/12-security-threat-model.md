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
| T1 | Spoofing: stolen or guessed passwords | Argon2id hashing; minimum 10 characters; login rate limit (10 per minute per client, real client IP only from `FORWARDED_ALLOW_IPS`); generic error messages; the same hashing work for unknown emails; cloud sign-up open only for the first account by default | `test_auth_tenancy.py`, `test_security.py` | No MFA or SSO yet (Phase 2); no account lockout beyond the rate limit |
| T2 | Spoofing: forged or stolen tokens | HS256 JWT signed with `SECRET_KEY` (32+ characters required in cloud mode); tokens expire (12 hours by default); the browser keeps the token in an HttpOnly, SameSite=Strict cookie that scripts cannot read (`__Host-` over HTTPS); tokens carry a session version, so sign out on all devices revokes them | Tests for invalid, expired, forged and revoked tokens and cookie flags | None known |
| T3 | Spoofing: another website or another program on the computer driving the passwordless local session | Loopback binding and a strict Host check (no test-only host names); a random key per launch is required to open a session and is delivered through a private redirect file; sessions from earlier launches are refused; every change needs the `X-Requested-With: mdos` header, which other sites cannot send | `test_security.py`, E2E "desktop access" tests, desktop smoke test | Cookies are shared across ports on 127.0.0.1 (as for Jupyter): avoid running untrusted local web servers while MDOS is open |
| T4 | Elevation: reading or changing another organization's project | Every project route resolves the project through membership (`project_access`) and every child entity through `get_owned(..., project_id)`; roles owner, editor, viewer; writes need editor | Cross-tenant tests return 404; verified again on PostgreSQL in the Docker image | Keep new routes on the same helpers (see AGENTS.md checklist) |
| T5 | Tampering: SQL injection | SQLAlchemy ORM with bound parameters only; no raw SQL built from input | Code review rule | None |
| T6 | Tampering: malicious upload (zip bombs, XML attacks, huge files) | Request bodies limited before and while they stream (uploads 26 MB, other requests 5 MB); row and column limits (100,000 by 500); XLSX expansion checked before parsing; `defusedxml` protections; uploads stored under generated keys, never user file names | Upload, body limit and zip bomb tests | Virus scanning is out of scope (files are parsed, never executed) |
| T7 | Tampering: spreadsheet formula injection in exports | Exported text cells beginning with `=`, `+`, `-`, `@` are neutralized | Questionnaire export tests | Apply the same helper to any new export |
| T8 | Tampering: cross-site scripting | React escapes all rendered text; strict CSP (`script-src 'self'`, no inline scripts, no third-party hosts); the HTML report export escapes every value and is served with a sandboxed CSP that allows no scripts | Header tests; E2E checks for CSP violations and the sandboxed export | None known |
| T9 | Tampering: prompt injection through reviews or open answers | Customer text is wrapped as untrusted data; agents can only call their allowlisted tools; the model never computes numbers, and drafted text is checked against the computed values (numeric grounding); causal wording is blocked without experimental evidence; everything the model drafts is labeled and needs human approval | `test_agents.py` with a fake adversarial provider | Continue red-teaming prompts as agent features grow |
| T10 | Repudiation: "I did not approve that" | Append-only audit log of every mutation with actor (person or agent), action and entity; approvals record who decided and when, with a rationale | Audit tests | Audit log export and retention settings (Phase 2) |
| T11 | Information disclosure: personal data in datasets or sent to Claude | Personal data detection (emails, Indonesian phone numbers, name-like columns) flagged as high severity; pseudonymization in the cleaning plan; emails, phone numbers and ID numbers masked before any prompt leaves the server; API responses are `no-store`; synthetic demo data is labeled everywhere | Quality and masking tests | Data retention policy and a data processing agreement template are business tasks |
| T12 | Information disclosure: secrets in the repository or client | `.env` is gitignored; empty values count as unset; API keys are only read server-side; the UI shows whether Claude is on, never the key; CI secret scan of tracked files (`scripts/check_secrets.py`, `--history` for all commits) | CI security job; full-history scan on 29 September 2026 found none | Rotate keys if they are ever pasted into an issue or chat |
| T13 | Information disclosure: verbose errors | Structured error responses without stack traces; server logs keep details | API tests check status codes and error shapes; handler reviewed | None |
| T14 | Denial of service: floods of logins, uploads or agent runs | Sliding-window limits for authentication, uploads and agent workflows; statistics capped by row and column limits; bootstrap resamples capped at 20,000 | Rate limit tests | The limiter is in-memory per process; use a shared store (Redis) or the proxy's limits when running several instances |
| T15 | Clickjacking, MIME sniffing and cross-origin leaks | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, COOP and CORP `same-origin`, Permissions-Policy, HSTS over HTTPS in cloud mode | Header tests | None known |
| T16 | Host header abuse and exposure in cloud mode | `ALLOWED_HOSTS` defaults to localhost; `CORS_ORIGINS="*"` is refused; Compose publishes the port on 127.0.0.1 only; the container runs as a non-root user with a read-only root filesystem, no new privileges and no capabilities; interactive API docs are off by default | Header tests, Docker smoke test | Set your public host name in production |
| T17 | Supply chain | Python dependencies pinned with hashes (`backend/requirements.txt`, wheels only in Docker); npm lockfile installed with `--ignore-scripts`; GitHub Actions pinned to commit hashes without persisted credentials; Dependabot; `pip-audit` and `npm audit` in CI; Node.js 24 LTS | CI security job | Sign desktop releases (owner's certificates) |

## 4. Local (desktop) mode specifics

* Data lives in the user's data folder; the JWT key is generated on first start and stored with owner-only
  permissions.
* The server only listens on 127.0.0.1 and refuses other Host headers, so other devices on the network and
  rebinding attacks cannot reach it. Opening a session also needs the key created at launch, which only the
  person who started MDOS receives (browser redirect file readable only by them, and the MDOS window).
* The desktop executable is not code-signed yet, so Windows SmartScreen and macOS Gatekeeper will warn. Signing
  certificates are a manual step for the owner (see the final summary in the repository README).

## 5. Cloud mode checklist before going live

1. Set a random `SECRET_KEY` (48+ characters) and keep it in the host's secret store.
2. Use PostgreSQL with TLS, daily backups and point-in-time recovery.
3. Terminate TLS at a proxy; set `ALLOWED_HOSTS` to the public host name and `FORWARDED_ALLOW_IPS` to the proxy's
   address (the app then sends HSTS and marks the session cookie Secure).
4. Leave `ALLOW_REGISTRATION` empty: only the first account can sign up. Set it to `true` only for an open,
   multi-workspace service (every stranger's workspace would use your Claude key).
5. Keep `CORS_ORIGINS` empty unless another domain must call the API.
6. Run more than one instance only with a shared rate limit store.
7. Review the privacy notice and consent text in the questionnaire with counsel for Indonesia's personal data
   protection law (UU PDP) before collecting real responses.
