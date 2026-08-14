#!/usr/bin/env python3
"""Sample the live H1 guest PC through the emulator's read-only debug API."""

from __future__ import annotations

import argparse
import collections
import json
import re
import time
import urllib.request
from pathlib import Path


PC_PATTERN = re.compile(r"\bpc=0x([0-9a-fA-F]+)")
EPC_PATTERN = re.compile(r"\bEPC\s+0x([0-9a-fA-F]+)")
EXCEPTION_VECTOR = 0x80000180
A320_ORIGIN = 0x80A00000
A320_BASE = 0x83D00000
A320_END = 0x83E45000


def registers(server: str) -> str:
    with urllib.request.urlopen(
        server.rstrip("/") + "/api/debug/registers", timeout=10
    ) as response:
        packet = json.load(response)
    return str(packet["registers"])


def region(address: int) -> str:
    if A320_BASE <= address < A320_END:
        return "a320_game"
    if 0x83C00000 <= address < A320_BASE:
        return "h1_bridge"
    if 0x80000000 <= address < 0x84000000:
        return "h1_firmware"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument("--samples", type=int, default=500)
    parser.add_argument("--interval", type=float, default=0.01)
    parser.add_argument("--output", type=Path, default=Path("build/7days-pc-profile.json"))
    args = parser.parse_args()
    if args.samples <= 0 or args.interval < 0:
        raise SystemExit("samples must be positive and interval must be non-negative")

    exact: collections.Counter[int] = collections.Counter()
    pages: collections.Counter[int] = collections.Counter()
    regions: collections.Counter[str] = collections.Counter()
    exceptions = 0
    failures: list[str] = []
    started = time.monotonic()
    for _ in range(args.samples):
        try:
            text = registers(args.server)
            pc_match = PC_PATTERN.search(text)
            epc_match = EPC_PATTERN.search(text)
            if not pc_match:
                raise ValueError("register response has no PC")
            address = int(pc_match.group(1), 16)
            if address == EXCEPTION_VECTOR and epc_match:
                address = int(epc_match.group(1), 16)
                exceptions += 1
            exact[address] += 1
            pages[address & ~0xFFF] += 1
            regions[region(address)] += 1
        except Exception as error:
            failures.append(f"{type(error).__name__}: {error}")
        if args.interval:
            time.sleep(args.interval)

    valid = sum(exact.values())

    def row(address: int, count: int, *, page: bool = False) -> dict[str, object]:
        item: dict[str, object] = {
            "address": f"0x{address:08X}",
            "count": count,
            "percent": round(100.0 * count / max(1, valid), 3),
            "region": region(address),
        }
        if A320_BASE <= address < A320_END:
            item["a320_original"] = f"0x{address - A320_BASE + A320_ORIGIN:08X}"
        if page:
            item["end"] = f"0x{address + 0xFFF:08X}"
        return item

    report = {
        "requested_samples": args.samples,
        "valid_samples": valid,
        "duration": round(time.monotonic() - started, 3),
        "exception_epc_samples": exceptions,
        "failures": failures[:20],
        "regions": {
            name: {
                "count": count,
                "percent": round(100.0 * count / max(1, valid), 3),
            }
            for name, count in regions.most_common()
        },
        "top_addresses": [row(address, count) for address, count in exact.most_common(50)],
        "top_pages": [
            row(address, count, page=True) for address, count in pages.most_common(50)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(json.dumps({key: value for key, value in report.items() if key not in {"top_addresses", "top_pages"}}, indent=2))
    print(json.dumps({"top_addresses": report["top_addresses"][:15]}, indent=2))
    return 0 if valid == args.samples else 1


if __name__ == "__main__":
    raise SystemExit(main())
