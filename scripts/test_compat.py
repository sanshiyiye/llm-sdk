from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CommandResult:
    name: str
    ok: bool
    output: str


def run_step(name: str, command: list[str], cwd: Path) -> CommandResult:
    shell_command = subprocess.list2cmdline(command)
    completed = subprocess.run(
        shell_command,
        cwd=cwd,
        text=True,
        capture_output=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return CommandResult(name=name, ok=completed.returncode == 0, output=output.strip())


def main() -> int:
    steps = [
        (
            "Python",
            [sys.executable, "-m", "pytest", "sdk/compat-tests/test_python_sdk.py", "-q"],
            ROOT,
        ),
        (
            "TypeScript Types",
            ["npm", "run", "test:compat:types"],
            ROOT / "sdk" / "typescript",
        ),
        (
            "TypeScript",
            ["npm", "run", "test:compat"],
            ROOT / "sdk" / "typescript",
        ),
        (
            "Go",
            ["go", "test", "-v"],
            ROOT / "sdk" / "compat-tests",
        ),
    ]

    results = [run_step(name, command, cwd) for name, command, cwd in steps]

    print("===== SDK Compat Report =====")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{result.name:<18} {status}")
    print("=============================")

    failed = [result for result in results if not result.ok]
    if not failed:
        return 0

    print()
    for result in failed:
        print(f"[{result.name}]")
        print(result.output)
        print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
