"""Fail if a tracked file contains something that looks like a real credential.

Usage (from the repository root):  python scripts/check_secrets.py            # files tracked by git
                                    python scripts/check_secrets.py --history  # every commit, before publishing
Runs in CI. Matches are reported by file and line with the value redacted; nothing is printed in full.
A line that must contain a look-alike (a test fixture) can end with the comment ``secret-scan: allow``.
"""

from __future__ import annotations

import re
import shutil
import subprocess  # noqa: S404 - runs git with fixed arguments
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW_MARKER = "secret-scan: allow"
PATTERNS = {
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "OpenAI API key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{32,}"),
    "GitHub token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "AWS access key": re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Stripe live key": re.compile(r"(?:sk|rk)_live_[0-9A-Za-z]{20,}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    "Connection string with password": re.compile(
        r"\b(?:postgres(?:ql)?(?:\+\w+)?|mysql|mongodb(?:\+srv)?)://[^\s:/@]+:(?P<secret>[^\s@/$]{6,})@"),
}
PLACEHOLDERS = re.compile(r"^(?:<.*>|\{.*\}|password|passwd|secret|changeme|example|x+|\*+)$", re.IGNORECASE)
FORBIDDEN_NAMES = re.compile(r"(?:^|/)(?:\.env(?:\.[\w-]+)?|id_rsa|id_ed25519|.+\.pem|.+\.p12|.+\.pfx|secret\.key)$")
ALLOWED_NAMES = {".env.example"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".xlsx", ".zip", ".pdf"}


def _redact(value: str) -> str:
    return value[:6] + "..." + value[-2:] if len(value) > 10 else "***"


def scan_text(name: str, text: str) -> list[str]:
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                if "secret" in pattern.groupindex and PLACEHOLDERS.match(match.group("secret")):
                    continue  # documentation placeholder such as user:password@host
                findings.append(f"{name}:{number}: {label} ({_redact(match.group(0))})")
    return findings


def _git(*args: str) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git was not found.")
    return subprocess.run([git, *args], cwd=ROOT, check=True, capture_output=True).stdout  # noqa: S603


def scan_tree() -> list[str]:
    files = _git("ls-files", "-z").split(b"\0")
    findings = []
    for raw in filter(None, files):
        name = raw.decode("utf-8", "replace")
        if FORBIDDEN_NAMES.search(name) and Path(name).name not in ALLOWED_NAMES:
            findings.append(f"{name}: this kind of file holds secrets and must not be committed")
            continue
        path = ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        findings += scan_text(name, path.read_text(encoding="utf-8", errors="ignore"))
    return findings


def scan_history() -> list[str]:
    log = _git("log", "--all", "-p", "--no-color", "--format=commit %H").decode("utf-8", "replace")
    findings, commit = [], "?"
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line.split()[1][:10]
        elif line.startswith("+") and not line.startswith("+++"):
            findings += [f.replace("history:1:", f"commit {commit}: ") for f in scan_text("history", line[1:])]
    return findings


def main() -> int:
    findings = scan_history() if "--history" in sys.argv else scan_tree()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} possible secret(s) found. Remove them, rotate any real credential, and commit again.")
        return 1
    print("No secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
