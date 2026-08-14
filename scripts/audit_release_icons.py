#!/usr/bin/env python3
"""Verify that every release game BDA has a non-placeholder H1 menu icon."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


SDK_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SDK_ROOT.parent
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from h1_bda.header import decode_header, read_c_string
from h1_bda.resources import (
    RESOURCE_OFFSET,
    RESOURCE_SIZES,
    RESOURCE_SPECS,
    build_diagnostic_resources,
)
from h1_bda.validate import validate_bda


DEFAULT_DIRECTORY = (
    WORKSPACE_ROOT
    / "deliverables"
    / "H1-real-hardware-test-2026-07-29"
    / "A-root"
    / "apps"
)


def inspect(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    validation = validate_bda(path)
    errors = list(validation["errors"])
    decoded = decode_header(raw)
    words = struct.unpack_from("<11I", decoded, 0)
    resource_offset = words[6]
    resource_sizes = tuple(words[7:11])
    payload_offset = words[5]
    if resource_offset != RESOURCE_OFFSET:
        errors.append(f"resource offset is 0x{resource_offset:x}")
    if resource_sizes != RESOURCE_SIZES:
        errors.append(f"resource sizes are {resource_sizes!r}")

    resources: list[dict[str, object]] = []
    offset = resource_offset
    for index, ((expected_width, expected_height, expected_bits), size) in enumerate(
        zip(RESOURCE_SPECS, resource_sizes)
    ):
        if offset + 12 > len(raw):
            errors.append(f"resource {index} header is outside the file")
            break
        width, height, bits, planes, draw_width, draw_height = struct.unpack_from(
            "<6H", raw, offset
        )
        expected = (expected_width, expected_height, expected_bits, 1)
        observed = (width, height, bits, planes)
        if observed != expected or (draw_width, draw_height) != (width, height):
            errors.append(f"resource {index} has image header {observed!r}")
        pixel_bytes = width * height * (bits // 8)
        pixels = raw[offset + 12 : offset + 12 + pixel_bytes]
        colors = {
            pixels[position : position + 2]
            for position in range(0, len(pixels), bits // 8)
        }
        if len(colors) < 4:
            errors.append(f"resource {index} contains only {len(colors)} colors")
        resources.append(
            {
                "index": index,
                "width": width,
                "height": height,
                "bits": bits,
                "colors": len(colors),
            }
        )
        offset += size

    region = raw[resource_offset:payload_offset]
    placeholder = region == build_diagnostic_resources()
    if placeholder:
        errors.append("icon is the SDK diagnostic placeholder")
    return {
        "file": path.name,
        "title": read_c_string(decoded[0x2C:0x3C]),
        "ok": not errors,
        "errors": errors,
        "placeholder": placeholder,
        "resource_sha256": hashlib.sha256(region).hexdigest().upper(),
        "resources": resources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--expected-count", type=int, default=18)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paths = sorted(args.directory.glob("*.bda"), key=lambda path: path.name.casefold())
    results = [inspect(path) for path in paths]
    errors: list[str] = []
    if len(results) != args.expected_count:
        errors.append(
            f"found {len(results)} BDA files, expected {args.expected_count}"
        )
    errors.extend(
        f"{item['file']}: {error}"
        for item in results
        for error in item["errors"]
    )
    report = {
        "format": "h1-release-icon-audit-v1",
        "ok": not errors,
        "expected_count": args.expected_count,
        "game_count": len(results),
        "errors": errors,
        "games": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
