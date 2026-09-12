"""Thin adapter around the documented Pome CLI.

Pome owns the authoritative request/state tape; this module only exports it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence


class PomeCLI:
    def __init__(self, executable: str = "pome") -> None:
        self.executable = executable

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            [self.executable, *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def start_twin(self, twin: str = "github") -> str:
        return self._run("twin", "start", twin)

    def inspect_latest(self) -> object:
        output = self._run("inspect", "latest")
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"format": "pome-cli-text", "raw": output}

    def export_latest(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.inspect_latest(), indent=2) + "\n")
        return destination


def main(argv: Sequence[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export the latest Pome server-side trace")
    parser.add_argument("--output", type=Path, default=Path("results/pome_trace.json"))
    parser.add_argument("--pome", default="pome")
    args = parser.parse_args(argv)
    print(PomeCLI(args.pome).export_latest(args.output))


if __name__ == "__main__":
    main()
