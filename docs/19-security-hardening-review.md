# 19. Security and safety hardening review (29 September 2026)

This pass applied the five prompts supplied by the owner: Anti-Harm Security and Safety Fixer v1, the Security and
Safety Repair Protocol, the Strict DevSecOps and Local Environment Guardian, the Defensive Security Engineering
master prompt and the Strict UI/UX constraints. It was defensive only: no exploit code, no attacks on live systems.

The prompts ask twelve questions before any change. The owner asked for the work to go ahead, so the answers below
come from the repository and the owner's instructions, choosing the most restrictive option wherever the prompts
say to. Every answer is marked **Confirm**: reply with a different answer and the defaults will change.

## 1. Pre-flight answers (Confirm)

| # | Question (merged across the prompts) | Answer |
|---|---|---|
| 1 | Project and attack surface | MDOS: a FastAPI and React app with agents. Surfaces: the web UI and API, file uploads, exports, the optional Claude call, the desktop launcher and the container. |
| 2 | Where it runs | End-user computers (desktop, loopback only), Docker behind a TLS proxy (cloud), CI runners and coding agents' sandboxes. |
| 3 | Sensitive data | Account emails and password hashes, survey answers and reviews that may contain names, emails and phone numbers, the JWT signing key, the optional `ANTHROPIC_API_KEY`, database passwords. None may appear in logs or git; personal identifiers must not leave the server. |
| 4 | File system boundaries | Write inside the repository only. At runtime, only the app data folder. Recursive deletion only of validated project storage folders and the E2E folder the test run created. Never home-directory secrets, other repositories or system paths. |
| 5 | Network boundaries | Inbound: 127.0.0.1 on the desktop; the container port published on 127.0.0.1, public only through a TLS proxy. Outbound at runtime: `api.anthropic.com` only, when a key is set. No fetches of user-supplied URLs. No CORS `*`. |
| 6 | Secrets management | Environment variables or an untracked `.env`; empty values in `.env.example`; a generated local key with owner-only permissions on the desktop; nothing in code, tests, logs or the frontend. |
| 7 | Auth and permissions | Cloud: accounts, organization isolation, owner/editor/viewer roles, sign-up for the first account only by default. Desktop: one local owner, gated by a per-launch key. |
| 8 | Dependency policy | No new packages without a reason (this pass added only two static font packages); npm without install scripts; Python pinned with hashes; no global installs, no `curl \| bash`. |
| 9 | Forbidden operations | `rm -rf` outside the allowlist, `shell=True` or `eval` with input, `sudo`, `chmod 777`, disabled TLS, CORS `*`, public binding without approval, force-pushing shared branches, skipping tests. |
| 10 | Data handling and retention | Parameterized queries only; generated storage keys; project deletion removes rows and files after the name is typed again; temporary test data removed after each run; personal identifiers masked before Claude. |
| 11 | Logging and audit | Log method, path and status, never bodies, headers, cookies or secrets. The append-only audit log records sign-ins, "sign out everywhere", approvals, deletions and every change. |
| 12 | Threat model and process | Attackers: an internet user, a signed-in user targeting another tenant, a malicious website, another program or account on the same computer, a compromised dependency, and the coding agent itself. Process: read-only audit first, then reversible, tested changes scoped to this repository, one change class per commit. |

## 2. Findings and fixes

Severity follows the Repair Protocol scale. "Your hands" lists what only the owner can do.

| ID | Severity | Asset | What could go wrong | Fix | Rollback | Your hands |
|---|---|---|---|---|---|---|
| H1 | High | Browser session | The sign-in token sat in `localStorage`, where any injected script could read it. | HttpOnly, SameSite=Strict cookie (`__Host-` over HTTPS); the app never sees the token. | Revert commit f592e07 | None |
| H2 | High | Desktop session | Any program or account on the same computer could open the passwordless session. | A random key per launch, delivered through a private redirect file; sessions end when MDOS closes. | Revert f592e07 | None |
| H3 | High | Container | Proxy headers were trusted from anyone and the port was published on every interface with `ALLOWED_HOSTS=*`, so client IPs (and rate limits) could be spoofed. | Headers trusted only from `FORWARDED_ALLOW_IPS`; port on 127.0.0.1; host allowlist by default; non-root, read-only root, no capabilities. | Revert ce88a79 | Set your proxy address and domain when deploying |
| M1 | Medium | Cookie changes | Moving to cookies without a CSRF defense would let other sites trigger changes. | `X-Requested-With: mdos` required on cookie-authenticated changes and on sign-in. | Revert f592e07 | None |
| M2 | Medium | Browser | No `script-src` policy; the report preview wrote HTML into a same-origin window. | Strict CSP; exports served sandboxed and opened as a normal link. | Revert f592e07 | None |
| M3 | Medium | Local host check | The test-only host name `testserver` was accepted in production. | Removed; tests use `localhost`. | Revert f592e07 | None |
| M4 | Medium | API docs | Interactive docs were on by default and loaded scripts from a CDN. | Off unless `ENABLE_API_DOCS=true`, with their own narrow CSP. | Revert f592e07 | None |
| M5 | Medium | Data deletion | One request deleted a project, and file cleanup trusted a computed path. | The name must be typed again (in the request body); cleanup only removes a validated `<org uuid>/<project uuid>` folder. | Revert f592e07, ce88a79 | None |
| M6 | Medium | Cloud sign-up | Open by default: strangers could create workspaces that spend the owner's Claude credit. | First account only unless `ALLOW_REGISTRATION=true`. | Set `ALLOW_REGISTRATION=true` | None |
| M7 | Medium | Personal data | Emails and phone numbers in answers and reviews reached Claude unmasked. | Masking at the provider boundary, counted in the agent trace. | Revert ce88a79 | None |
| M8 | Medium | Availability | No request size limit; an XLSX could expand without bound. | Body limits before and during streaming; XLSX expansion check. | Revert ce88a79 | None |
| M9 | Medium | Supply chain | Actions pinned by tag, Python versions floating, npm install scripts allowed. | Commit-pinned actions, hash-pinned Python, `--ignore-scripts`, Dependabot, audits in CI. | Revert fa69499 | Turn on the GitHub settings in section 5 |
| M10 | Medium | Dependencies | Known advisories: react-router open redirect (runtime), Vite, Vitest and esbuild dev-server issues. | Upgraded; `npm audit` and `pip-audit` report none. | Revert fa69499 | None |
| M11 | Medium | Toolchain | Node.js 20 reached end of life in April 2026. | CI and Docker on Node.js 24 LTS. | Revert fa69499 | None |
| L1 | Low | Tests | A fixed signing key lived in the test fixtures. | Generated per test run. | Revert f592e07 | None |
| L2 | Low | Accounts | Login response time revealed whether an email had an account. | The same hashing work for unknown emails. | Revert ce88a79 | None |
| L3 | Low | Local traces | Each E2E run left a data folder in the temp directory. | A teardown removes the run's own folder; old folders were deleted (section 4). | Revert f592e07 | None |
| L4 | Low | Build script | `shell=True` on Windows. | Resolved program path, no shell. | Revert fa69499 | None |
| L5 | Low | Configuration | `.env.example` suggested `ALLOWED_HOSTS=*` and open sign-up; blank values counted as set. | Safe examples; empty values count as unset. | Revert ce88a79 | None |
| L6 | Low | Headers | No Permissions-Policy, COOP, CORP, HSTS or `no-store`. | Added. | Revert f592e07 | None |
| L7 | Low | Launcher | The private link file stayed on disk after SIGTERM. | Removed on SIGTERM, SIGHUP and Ctrl+C. | Revert fa69499 | None |
| M12 | Medium | Desktop data folder | The folder was created readable by other accounts (755), so on a shared Mac or Linux computer they could read the database and uploads. | Created owner-only (700) and tightened at start in desktop mode; `/data` is 700 in the image. | Revert the second review commit | None |
| M13 | Medium | Desktop settings | A `.env` file in the folder MDOS was started from was read, so a planted file could point the app at another database. | The desktop launcher ignores `.env` files; developers running from source still use theirs. | Same | None |
| L8 | Low | Desktop cookie | The session cookie was kept on disk for 12 hours. | A browser-session cookie in desktop mode (tokens from earlier launches were already refused). | Same | None |
| L9 | Low | Desktop server | Responses announced `server: uvicorn`. | Header removed, as in the Docker image. | Same | None |
| L10 | Low | CI logs | The desktop smoke test's throwaway key appeared in public logs. | Masked with `::add-mask::`; CI also verifies npm registry signatures. | Same | None |
| L11 | Low | Robustness | Two `assert` statements guarded database setup (removed under `python -O`). | Explicit errors. | Same | None |
| M14 | Medium | Cloud settings | `docker-compose.yml` passed only some settings to the app, so `COOKIE_SECURE`, the limits and the model options set in `.env` were silently ignored. Inside Docker a proxy on the same host connects from the Compose network's gateway, so the documented `FORWARDED_ALLOW_IPS=127.0.0.1` never matched it and, behind TLS, the session cookie was not marked Secure. | Compose passes every documented setting (empty values keep the defaults); the deployment guide, `.env.example` and SECURITY.md recommend `COOKIE_SECURE=true` and explain how to find the gateway address. | Revert the manual commit | Set `COOKIE_SECURE=true` and the gateway address when deploying |

No live secret was found in the working tree or in any commit, so nothing needs rotating.

## 3. Proof

| Check | Result |
|---|---|
| Secret scan of tracked files and full history (`scripts/check_secrets.py`, `--history`) | 0 findings; a planted fake key and database URL were caught and printed redacted |
| Python dependencies (`pip-audit` on `backend/requirements.txt` and on the installed environment) | No known vulnerabilities |
| npm dependencies (`npm audit`) | 0 vulnerabilities |
| Banned patterns (`shell=True`, `eval`, `exec`, `os.system`, `verify=False`, CORS `*`, token storage, header or cookie logging) | None in application code; subprocesses only in build scripts with fixed arguments |
| Deletion paths | Three, each guarded: storage (UUID and depth checks, tested with `..` paths), the launcher file, the E2E folder (temp-directory prefix check) |
| Static analysis (Ruff with the Bandit `S` rules, all rules forced on) | No findings after replacing two `assert` statements |
| Live server probe (plain HTTP requests against a running desktop server) | Headers, no-store, key gating, cookie flags, CSRF refusal, host check, docs off, no cross-site CORS, 413 for large bodies, owner-only folder: all as designed |
| Personal data in the repository | None: sample emails use the reserved `example.com` domain, no phone or ID numbers, commits are authored by `noreply` addresses, the Excel sample's metadata names only openpyxl |
| Outbound calls | The Anthropic SDK only; the launcher's health check is a fixed loopback URL; the web app calls its own origin |
| Backend tests (SQLite and PostgreSQL in CI) | 87 passed, including 25 security tests |
| Frontend unit tests | 7 passed, including the no-shadow, no-gradient guard |
| End-to-end tests | 13 passed: locked desktop screen, wrong key refused, HttpOnly Strict cookie, cookie without header refused, sandboxed export, phone widths |
| Desktop builds (Windows, macOS, Linux) | Built and smoke-tested with the launch key, the session cookie and the demo |
| Docker image | Built and smoke-tested with a read-only root filesystem and no capabilities |

## 4. Local traces removed

* The temporary E2E data folders left by earlier runs in the system temp directory (`mdos-e2e-*`), after checking
  each one only held MDOS test data.
* Pytest's temporary folders (`/tmp/pytest-of-root`).
* Scratch files from this review (screenshots, a throwaway database and a review server) in the session's scratch
  folder.

## 5. What the owner should do

1. In GitHub, **Settings, Code security**: turn on secret scanning, push protection, Dependabot alerts, Dependabot
   security updates, private vulnerability reporting and CodeQL (default setup).
2. Choose the default branch you will release from and protect it: require pull requests, the CI checks and a
   review; block force pushes and deletion.
3. Dependabot's first pull requests (#1 to #5) are closed, and the Playwright update from #5 is in the branch. Delete
   the leftover branch `dependabot/npm_and_yarn/frontend/frontend-dev-tools-a948c343a0` and turn on **Automatically
   delete head branches** (Settings, General).
4. When deploying the cloud version: set `SECRET_KEY`, your domain in `ALLOWED_HOSTS`, `COOKIE_SECURE=true` and your
   proxy's address as the container sees it in `FORWARDED_ALLOW_IPS` (docs/13-deployment.md), and keep
   `ALLOW_REGISTRATION` empty.
5. Sign the desktop releases (Windows code signing, Apple Developer ID and notarization) so users do not see
   SmartScreen or Gatekeeper warnings.
6. Confirm or change the answers in section 1 and in [18-interface-brief.md](18-interface-brief.md).
