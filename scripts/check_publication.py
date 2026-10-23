"""Read-only publication scan. Reports paths/categories, never secret values.

This heuristic is not a comprehensive secret or license audit.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    from dotenv import dotenv_values
    env = dotenv_values(ROOT / ".env")
    secrets = [v.encode() for k, v in env.items() if v and len(v) >= 12
               and any(word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
    pattern = re.compile(rb"(?:sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
    findings = []
    seen = set()
    for revision in git("rev-list", "--all").decode().splitlines():
        for entry in git("ls-tree", "-rz", revision).split(b"\0"):
            if not entry:
                continue
            info, name = entry.split(b"\t", 1)
            oid = info.split()[-1].decode()
            if oid in seen:
                continue
            seen.add(oid)
            data = git("cat-file", "blob", oid)
            if pattern.search(data) or any(secret in data for secret in secrets):
                findings.append({"revision": revision[:7], "path": name.decode(), "category": "secret_candidate"})
    tracked = git("ls-files", "-z").decode().split("\0")
    current = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    large = []
    for name in filter(None, current):
        path = ROOT / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if pattern.search(data) or any(secret in data for secret in secrets):
            findings.append({"path": name, "category": "secret_candidate_worktree"})
        if len(data) > 5 * 1024 * 1024:
            large.append({"path": name, "bytes": len(data)})
    report = {"secret_candidates": findings, "files_over_5_mib": large,
              "tracked_runtime_or_asset_files": [p for p in tracked if p and (
                  p.startswith(("data/", "logs/", ".venv/")) and not p.endswith(".gitkeep")
                  or p.endswith((".env", ".sqlite3", ".pem")))],
              "known_credential_values_checked": len(secrets),
              "scope": "All locally reachable commit blobs and nonignored working-tree files; no remote refs fetched."}
    print(json.dumps(report, indent=2))
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())
