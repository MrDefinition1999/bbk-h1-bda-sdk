#!/usr/bin/env python3
"""Extract one file from the H1 emulator FAT/FTL NAND image."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEPLOY_SCRIPT = SCRIPT_DIR / "deploy_emulator_bda.py"


def load_deployment_module():
    spec = importlib.util.spec_from_file_location("h1_deploy_for_extract", DEPLOY_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(DEPLOY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalize(value: str) -> str:
    return "/" + value.replace("\\", "/").strip("/").casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="guest FAT path or unique file name")
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument(
        "--nand",
        type=Path,
        default=SCRIPT_DIR.parents[1]
        / "emulator"
        / "windows-x86_64"
        / "firmware"
        / "h1-system.raw",
    )
    args = parser.parse_args()
    deployment = load_deployment_module()
    requested = normalize(args.path)

    with deployment.H1Fat16(args.nand.resolve()) as volume:
        entries = [entry for entry in volume.entries() if not entry.is_directory]
        exact = [entry for entry in entries if normalize(entry.path) == requested]
        if not exact and "/" not in args.path.replace("\\", "/").strip("/"):
            exact = [entry for entry in entries if entry.name.casefold() == args.path.casefold()]
        if len(exact) != 1:
            raise FileNotFoundError(
                f"expected one H1 file for {args.path!r}, found {len(exact)}"
            )
        data = volume.read_file(exact[0])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"path={exact[0].path}")
    print(f"size={len(data)}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
