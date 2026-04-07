from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class StepResult:
    name: str
    ok: bool
    output: str


def run_step(name: str, command: list[str], cwd: Path) -> StepResult:
    completed = subprocess.run(
        subprocess.list2cmdline(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )
    return StepResult(
        name=name,
        ok=completed.returncode == 0,
        output=((completed.stdout or "") + (completed.stderr or "")).strip(),
    )


def main() -> int:
    steps = [
        ("ConfigMap Sync", [sys.executable, "scripts/generate_k8s_configmap.py", "--check"], ROOT),
        ("Compat", [sys.executable, "scripts/test_compat.py"], ROOT),
        ("Python Unit", [sys.executable, "-m", "pytest", "sdk/python/tests", "-q"], ROOT),
        ("Python Build", [sys.executable, "-m", "build", "--sdist", "--wheel"], ROOT / "sdk" / "python"),
        ("TypeScript Test", ["npm", "test"], ROOT / "sdk" / "typescript"),
        ("TypeScript Lint", ["npm", "run", "lint"], ROOT / "sdk" / "typescript"),
        ("TypeScript Build", ["npm", "run", "build"], ROOT / "sdk" / "typescript"),
        ("TypeScript Pack", ["npm", "pack", "--dry-run"], ROOT / "sdk" / "typescript"),
        ("Go Unit", ["go", "test", "./..."], ROOT / "sdk" / "go"),
        ("Go Compat", ["go", "test", "-v"], ROOT / "sdk" / "compat-tests"),
    ]

    results = [run_step(name, command, cwd) for name, command, cwd in steps]
    print("===== Release Readiness Report =====")
    for result in results:
        print(f"{result.name:<18} {'PASS' if result.ok else 'FAIL'}")
    print("====================================")

    failures = [result for result in results if not result.ok]
    if not failures:
        return 0

    print()
    for result in failures:
        print(f"[{result.name}]")
        print(result.output)
        print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
