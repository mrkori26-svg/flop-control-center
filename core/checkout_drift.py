from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def inspect_checkout(root: Path, repo_name: str) -> dict[str, object]:
    repo = root / repo_name
    if not (repo / ".git").exists():
        return {"repo": repo_name, "root": str(root), "status": "MISSING"}
    head = _git(repo, "rev-parse", "HEAD")
    branch = _git(repo, "branch", "--show-current")
    dirty = bool(_git(repo, "status", "--porcelain"))
    return {
        "repo": repo_name,
        "root": str(root),
        "status": "PRESENT",
        "head": head,
        "branch": branch or None,
        "dirty": dirty,
    }


def compare_roots(roots: list[Path], repo_names: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for repo_name in repo_names:
        rows = [inspect_checkout(root, repo_name) for root in roots]
        present = [row for row in rows if row["status"] == "PRESENT"]
        heads = {str(row["head"]) for row in present}
        dirty = any(bool(row.get("dirty")) for row in present)
        if not present:
            state = "MISSING"
        elif len(heads) > 1:
            state = "DIVERGED"
        elif dirty:
            state = "DIRTY"
        else:
            state = "ALIGNED"
        findings.append({"repo": repo_name, "state": state, "checkouts": rows})
    return findings
