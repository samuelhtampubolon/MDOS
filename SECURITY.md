# Security policy

## 1. Supported versions

| Version | Supported |
|---|---|
| 0.1.x (current branch) | Yes |
| Anything older | No |

## 2. Reporting a vulnerability

Please report privately, never in a public issue, pull request or discussion.

1. Open the repository's **Security** tab and choose **Report a vulnerability** (GitHub private vulnerability
   reporting).
2. Describe what is affected and how you noticed it. Do not include real credentials or personal data; if a secret
   is involved, say where it is, not what it is.
3. You will get an answer within 7 days. Fixes for confirmed issues are released as soon as they are verified, and
   reporters are credited unless they ask not to be.

Please test only against your own installation. Do not access other people's data or degrade a service.

## 3. What the application protects

| Area | Protection | Where |
|---|---|---|
| Sessions | HttpOnly, SameSite=Strict cookie (`__Host-` prefixed over HTTPS). Changes need the `X-Requested-With: mdos` header, which other sites cannot send. Tokens carry an account session version, so "sign out on all devices" revokes them all. | `backend/mdos/security.py`, `deps.py`, `api/auth.py` |
| Desktop mode | Bound to 127.0.0.1 with a trusted-host check. A random key is created at every launch and reaches the browser through a private (0600) redirect file, not the command line; the session cookie ends with the browser session and is refused once MDOS restarts. The data folder is owner-only (0700), and a `.env` file in the folder MDOS starts from is ignored. | `backend/mdos/desktop.py`, `config.py` |
| Browser | Strict Content Security Policy (no inline scripts, no third-party requests), `frame-ancestors 'none'`, COOP and CORP, Permissions-Policy, `no-store` on API responses, HSTS over HTTPS. HTML report exports are served sandboxed. | `backend/mdos/main.py`, `api/reports.py` |
| Accounts (cloud) | Argon2id passwords, login rate limit, equal work for unknown emails, sign-up open only for the first account unless `ALLOW_REGISTRATION=true`. | `api/auth.py`, `ratelimit.py` |
| Tenancy | Every project route checks organization and role; other organizations' projects answer "not found". | `deps.py` |
| Data | Upload size and shape limits, request body limits (also for streamed bodies), XLSX expansion checks, spreadsheet formula neutralizing in exports, generated storage keys, confirmed project deletion that only removes `<org uuid>/<project uuid>` folders. | `bodylimit.py`, `services/datasets.py`, `storage.py` |
| Claude (optional) | Off without `ANTHROPIC_API_KEY`. Emails, phone numbers and ID numbers are masked before sending. The model has no tools; its output is validated before use. | `mdos/privacy.py`, `agents/providers.py` |
| Supply chain | Python dependencies pinned with hashes, npm installed with `--ignore-scripts`, GitHub Actions pinned to commit hashes, Dependabot, `pip-audit`, `npm audit` and a secret scan in CI. | `backend/requirements.txt`, `.github/` |

The threat model is in [docs/12-security-threat-model.md](docs/12-security-threat-model.md) and the latest review in
[docs/19-security-hardening-review.md](docs/19-security-hardening-review.md).

## 4. Safe configuration (cloud)

| Setting | Safe value |
|---|---|
| `SECRET_KEY` | 48 or more random characters from your secret store (the app refuses to start without 32) |
| `ALLOWED_HOSTS` | Your public host name(s); never `*` unless your proxy checks hosts |
| `FORWARDED_ALLOW_IPS` | Your reverse proxy's address as the app sees it, never `*` (in Docker, the Compose network's gateway for a proxy on the same host; see docs/13-deployment.md) |
| `ALLOW_REGISTRATION` | Empty (first account only) or `false` |
| `CORS_ORIGINS` | Empty; `*` is refused |
| `ENABLE_API_DOCS` | `false` |
| `COOKIE_SECURE` | `true` behind a TLS proxy |

## 5. Sandbox rules for contributors and AI coding agents

These rules apply to people and to coding agents (Claude Code, Codex, Antigravity, Grok Build and others). Treat an
agent as an untrusted operator with shell access: it follows these rules, and reviewers check that it did.

**Files**

* Write only inside this repository. At runtime the app writes only to its data folder (`MDOS_DATA_DIR`: the user
  data folder on the desktop, `/data` in Docker).
* Every stored file goes through `backend/mdos/storage.py` (`_safe_path`), which resolves the path and refuses
  anything outside the storage root. User-supplied file names are never used as paths.
* Recursive deletion is allowed only for a validated `<org uuid>/<project uuid>` folder inside storage, and for the
  E2E temporary folder that the test run created itself (`frontend/e2e/teardown.ts`). A new delete path needs the
  same allowlist check and a test.
* Never touch `~/.ssh`, `~/.aws`, password managers, other repositories or system folders.

**Network**

* Runtime outbound traffic: only `api.anthropic.com`, through the official SDK, and only when `ANTHROPIC_API_KEY` is
  set. The app never fetches a URL that a user supplied.
* Build-time traffic: PyPI, the npm registry and GitHub.
* Inbound: the desktop build binds 127.0.0.1 only; the container binds 0.0.0.0 inside the container and Compose
  publishes it on the host's 127.0.0.1.
* To add an outbound host: explain why in the pull request, call it with a timeout, validate the host name against a
  fixed allowlist, refuse private and loopback addresses, add a test that a blocked host is refused, and list it
  above.

**Secrets**

* Secrets live in environment variables or `.env` (untracked). `.env.example` keeps secret values empty.
* Never print, log or paste secrets, cookies, `Authorization` headers or personal data; redact to the last 4
  characters if a value must be referenced.
* Run `python scripts/check_secrets.py` before committing (CI runs it too; `--history` scans every commit).
* If a real secret is ever committed, rotate it at the provider first; removing it from the history comes second.

**Commands and dependencies**

* No `sudo`, `chmod 777`, `curl | bash`, global installs, `eval` or shell commands built from input. Subprocesses use
  a fixed argument list and a resolved program path, never `shell=True`.
* Never disable TLS verification, set CORS to `*`, relax the trusted-host check or bypass the CSRF header "just to
  test". Fix the cause instead.
* New dependencies need a reason in the pull request. Install npm packages with `--ignore-scripts`; regenerate
  `backend/requirements.txt` with hashes using the command at the top of that file. CI must stay free of known
  vulnerabilities.
* Never `git push --force` to a shared branch, and never skip or disable a test to get CI green.

**Interface**

* Follow [docs/09-design-system.md](docs/09-design-system.md): no shadows, gradients or scale transforms (a unit test
  enforces this), status colors always with an icon and a label, a table view for every chart, visible focus.
