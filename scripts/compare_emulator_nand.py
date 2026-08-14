#!/usr/bin/env python3
"""Compare files in two H1 FAT/FTL NAND images."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEPLOY_SCRIPT = SCRIPT_DIR / "deploy_emulator_bda.py"


def load_deployment_module():
    spec = importlib.util.spec_from_file_location("h1_deploy_for_compare", DEPLOY_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(DEPLOY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def inventory(deployment, nand: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    with deployment.H1Fat16(nand.resolve()) as volume:
        for entry in volume.entries():
            if entry.is_directory:
                continue
            data = volume.read_file(entry)
            result[entry.path.casefold()] = {
                "path": entry.path,
                "size": entry.size,
                "sha256": hashlib.sha256(data).hexdigest().upper(),
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    deployment = load_deployment_module()
    before = inventory(deployment, args.before)
    after = inventory(deployment, args.after)
    before_paths = set(before)
    after_paths = set(after)
    changed = [
        {"before": before[path], "after": after[path]}
        for path in sorted(before_paths & after_paths)
        if before[path]["sha256"] != after[path]["sha256"]
    ]
    report = {
        "format": "h1-nand-file-diff-v1",
        "before": str(args.before.resolve()),
        "after": str(args.after.resolve()),
        "before_files": len(before),
        "after_files": len(after),
        "added": [after[path] for path in sorted(after_paths - before_paths)],
        "removed": [before[path] for path in sorted(before_paths - after_paths)],
        "changed": changed,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
