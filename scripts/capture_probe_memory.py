#!/usr/bin/env python3
"""Read a bounded guest physical-memory range through the emulator REST API."""

from __future__ import annotations

import argparse
import json
import re
import struct
import urllib.parse
import urllib.request
from pathlib import Path


WORD = re.compile(r"0x([0-9a-fA-F]{8})")


def read_words(server: str, address: int, count: int) -> list[int]:
    output: list[int] = []
    while len(output) < count:
        chunk = min(80, count - len(output))
        current = address + len(output) * 4
        query = urllib.parse.urlencode({"address": hex(current), "count": chunk})
        with urllib.request.urlopen(
            server.rstrip("/") + "/api/debug/memory?" + query,
            timeout=10,
        ) as response:
            data = json.load(response)
        if "error" in data:
            raise RuntimeError(data["error"])
        words = [int(value, 16) for value in WORD.findall(str(data["memory"]))]
        if len(words) < chunk:
            raise RuntimeError(
                f"memory response at 0x{current:08X} has {len(words)} words, expected {chunk}: "
                f"{data['memory']!r}"
            )
        output.extend(words[-chunk:])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("address", type=lambda value: int(value, 0))
    parser.add_argument("size", type=lambda value: int(value, 0))
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    args = parser.parse_args()
    if args.address & 3 or args.size <= 0:
        parser.error("address must be word-aligned and size must be positive")

    words = read_words(args.server, args.address, (args.size + 3) // 4)
    data = b"".join(struct.pack("<I", value) for value in words)[: args.size]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"address=0x{args.address:08X}")
    print(f"size={len(data)}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
