#!/usr/bin/env python3
"""Validate the H1 BDA envelope, menu resources, and payload boundaries."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from .header import (
    CHECKSUM_OFFSET,
    HEADER_SIZE,
    MAGIC,
    MARKER,
    VERSION,
    decode_header,
    read_c_string,
)


def _empty_report(path: Path, size: int, errors: list[str]) -> dict[str, object]:
    return {
        "path": str(path),
        "size": size,
        "title": "",
        "category": None,
        "payload_offset": None,
        "resource_offset": None,
        "resource_sizes": [],
        "resources": [],
        "checksum_ok": False,
        "errors": errors,
        "warnings": [],
        "ok": False,
    }


def validate_bda(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    errors: list[str] = []
    warnings: list[str] = []
    if len(data) < HEADER_SIZE:
        return _empty_report(
            path,
            len(data),
            [f"file is shorter than the 0x{HEADER_SIZE:x}-byte H1 header"],
        )

    decoded = decode_header(data)
    words = struct.unpack_from("<11I", decoded, 0)
    (
        magic,
        marker,
        version,
        category,
        file_size_minus_4,
        payload_offset,
        resource_offset,
        *resource_sizes,
    ) = words
    stored_checksum = struct.unpack_from("<I", decoded, CHECKSUM_OFFSET)[0]
    computed_checksum = sum(decoded[:CHECKSUM_OFFSET]) & 0xFFFFFFFF
    checksum_ok = stored_checksum == computed_checksum

    if magic != MAGIC:
        errors.append(f"magic is 0x{magic:08x}, expected 0x{MAGIC:08x}")
    if marker != MARKER:
        errors.append(f"marker is 0x{marker:08x}, expected 0x{MARKER:08x}")
    if version != VERSION:
        warnings.append(f"version is 0x{version:08x}, expected 0x{VERSION:08x}")
    if category == 0 or category > 0xFFFF:
        errors.append(f"category 0x{category:x} is outside the observed H1 range")
    if file_size_minus_4 != len(data) - 4:
        errors.append(
            f"file_size_minus_4 is 0x{file_size_minus_4:x}, "
            f"expected 0x{len(data) - 4:x}"
        )
    if not checksum_ok:
        errors.append(
            f"header checksum is 0x{stored_checksum:08x}, "
            f"expected 0x{computed_checksum:08x}"
        )

    if resource_offset < HEADER_SIZE or resource_offset > len(data):
        errors.append(f"resource offset 0x{resource_offset:x} is outside the file")
    if payload_offset < HEADER_SIZE or payload_offset >= len(data):
        errors.append(f"payload offset 0x{payload_offset:x} is outside the file")
    if payload_offset & 3:
        errors.append(f"payload offset 0x{payload_offset:x} is not 4-byte aligned")
    if resource_offset > payload_offset:
        errors.append("resource offset follows the payload offset")

    resources: list[dict[str, int]] = []
    cursor = resource_offset
    for index, size in enumerate(resource_sizes):
        start = cursor
        end = start + size
        resource = {"index": index, "start": start, "end": end, "size": size}
        resources.append(resource)
        if size < 12:
            errors.append(f"resource {index} size 0x{size:x} is shorter than its image header")
        elif start < HEADER_SIZE or end > len(data) or end > payload_offset:
            errors.append(
                f"resource {index} range 0x{start:x}..0x{end:x} is outside its region"
            )
        else:
            width, height, bits, planes, draw_width, draw_height = struct.unpack_from(
                "<6H", data, start
            )
            resource.update(
                {
                    "width": width,
                    "height": height,
                    "bits": bits,
                    "planes": planes,
                    "draw_width": draw_width,
                    "draw_height": draw_height,
                }
            )
            if width == 0 or height == 0:
                errors.append(f"resource {index} has an empty image")
            if bits not in (16, 24):
                errors.append(f"resource {index} uses unsupported {bits}-bit pixels")
            if planes != 1:
                errors.append(f"resource {index} has {planes} planes")
            if (draw_width, draw_height) != (width, height):
                errors.append(f"resource {index} draw dimensions do not match its image")
            if bits in (16, 24):
                required = 12 + width * height * (bits // 8)
                if required > size:
                    errors.append(
                        f"resource {index} requires 0x{required:x} bytes, has 0x{size:x}"
                    )
        cursor = end

    if resource_offset <= payload_offset and cursor != payload_offset:
        relation = "overlaps" if cursor > payload_offset else "does not reach"
        errors.append(
            f"resource region ends at 0x{cursor:x} and {relation} payload 0x{payload_offset:x}"
        )

    if 0 <= payload_offset <= len(data) - 4:
        entry_word = data[payload_offset : payload_offset + 4]
        if entry_word in (b"\x00" * 4, b"\xFF" * 4):
            warnings.append("payload begins with an empty or erased MIPS instruction")

    return {
        "path": str(path),
        "size": len(data),
        "title": read_c_string(decoded[0x2C:0x3C]),
        "description": read_c_string(decoded[0x50:0x64]),
        "category": category,
        "version": version,
        "file_size_minus_4": file_size_minus_4,
        "payload_offset": payload_offset,
        "resource_offset": resource_offset,
        "resource_sizes": resource_sizes,
        "resources": resources,
        "checksum": stored_checksum,
        "expected_checksum": computed_checksum,
        "checksum_ok": checksum_ok,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bda", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_bda(args.bda)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"file={report['path']}")
        print(f"size=0x{int(report['size']):x}")
        print(f"title={report.get('title', '')}")
        for warning in report["warnings"]:
            print(f"warning: {warning}")
        for error in report["errors"]:
            print(f"error: {error}")
        print("result=" + ("PASS" if report["ok"] else "FAIL"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
