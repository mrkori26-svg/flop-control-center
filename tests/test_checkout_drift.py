from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from core.checkout_drift import compare_roots


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def make_repo(path: Path, content: str) -> None:
    path.mkdir(parents=True)
    run("git", "init", "-q", cwd=path)
    run("git", "config", "user.email", "test@example.invalid", cwd=path)
    run("git", "config", "user.name", "Test", cwd=path)
    (path / "file.txt").write_text(content, encoding="utf-8")
    run("git", "add", "file.txt", cwd=path)
    run("git", "commit", "-qm", "init", cwd=path)


class CheckoutDriftTests(unittest.TestCase):
    def test_detects_diverged_heads(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_repo(base / "a" / "repo", "a")
            make_repo(base / "b" / "repo", "b")
            result = compare_roots([base / "a", base / "b"], ["repo"])
            self.assertEqual(result[0]["state"], "DIVERGED")
