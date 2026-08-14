#!/usr/bin/env python3
"""Transactionally add one new 8.3 file to the H1 emulator FAT16 root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from datetime import datetime
from pathlib import Path

import deploy_emulator_bda as deployment


def free_root_entry(volume: deployment.H1Fat16) -> int:
    root = volume.reader.read(volume.geometry.root_offset, volume.geometry.root_size)
    for offset in range(0, len(root), 32):
        if root[offset] in {0x00, 0xE5}:
            return volume.geometry.root_offset + offset
    raise ValueError("H1 FAT16 root directory has no free entry")


def dos_timestamp(now: datetime) -> tuple[int, int]:
    year = max(1980, min(2107, now.year))
    date = ((year - 1980) << 9) | (now.month << 5) | now.day
    stamp = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    return date, stamp


def install(nand: Path, source: Path, name: str, helper: Path) -> dict[str, object]:
    payload = source.read_bytes()
    if not payload:
        raise ValueError("refusing to install an empty H1 root file")
    short_name = deployment.encode_short_name(name)
    changed: dict[int, bytearray] = {}
    with deployment.H1Fat16(nand) as volume:
        if any(entry.path.casefold() == f"/{name}".casefold() for entry in volume.entries()):
            raise FileExistsError(f"/{name} already exists in the H1 volume")
        count = deployment.required_cluster_count(len(payload), volume.geometry.cluster_size)
        chain = deployment.select_free_clusters(volume, count)
        for index, cluster in enumerate(chain):
            next_cluster = chain[index + 1] if index + 1 < len(chain) else 0xFFFF
            deployment.patch_fat_entry(changed, volume, cluster, next_cluster)
        capacity = len(chain) * volume.geometry.cluster_size
        padded = payload + bytes(capacity - len(payload))
        for index, cluster in enumerate(chain):
            start = index * volume.geometry.cluster_size
            deployment.patch_unit(
                changed,
                volume,
                volume.cluster_offset(cluster),
                padded[start : start + volume.geometry.cluster_size],
            )

        date, stamp = dos_timestamp(datetime.now())
        entry = bytearray(32)
        entry[:11] = short_name
        entry[11] = 0x20
        struct.pack_into("<H", entry, 14, stamp)
        struct.pack_into("<H", entry, 16, date)
        struct.pack_into("<H", entry, 22, stamp)
        struct.pack_into("<H", entry, 24, date)
        struct.pack_into("<H", entry, 26, chain[0])
        struct.pack_into("<I", entry, 28, len(payload))
        directory_offset = free_root_entry(volume)
        deployment.patch_unit(changed, volume, directory_offset, entry)
        records, new_ftl_records = deployment.allocate_ftl_records(
            volume.scan, set(changed)
        )

    with nand.open("r+b", buffering=0) as output, deployment.build_nand.EccEncoder(helper) as encoder:
        for logical in sorted(changed):
            record = records[logical]
            deployment.build_nand.write_mapped_unit(
                output,
                record,
                logical,
                bytes(changed[logical]),
                1 if logical in new_ftl_records else ((record.sequence or 0) + 1) & 0xFFFF,
                encoder,
            )
        output.flush()
        os.fsync(output.fileno())

    with deployment.H1Fat16(nand) as verified:
        matches = [
            entry
            for entry in verified.entries()
            if not entry.is_directory and entry.path.casefold() == f"/{name}".casefold()
        ]
        if len(matches) != 1:
            raise ValueError(f"installed /{name} did not resolve uniquely")
        actual = verified.read_file(matches[0])
        if actual != payload:
            raise ValueError(f"installed /{name} failed byte-for-byte read-back")
        bad_records = [
            record
            for record in verified.scan.records
            if record.kind in {"bad", "invalid", "torn"}
        ]
        if bad_records:
            raise ValueError(f"installation produced {len(bad_records)} invalid FTL records")
        generations = {
            str(logical): verified.scan.mapping[logical].sequence
            for logical in sorted(changed)
        }

    return {
        "nand": str(nand.resolve()),
        "source": str(source.resolve()),
        "target": f"/{name}",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "clusters": len(chain),
        "cluster_capacity": capacity,
        "first_cluster": chain[0],
        "directory_entry_offset": directory_offset,
        "allocated_ftl_units": {
            str(logical): record.physical_block
            for logical, record in sorted(new_ftl_records.items())
        },
        "changed_logical_units": sorted(changed),
        "verified_generations": generations,
        "readback_match": True,
        "invalid_ftl_records": 0,
    }


def install_transactionally(
    nand: Path, source: Path, name: str, helper: Path
) -> dict[str, object]:
    temporary = nand.with_name(nand.name + ".install.tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        deployment.copy_file(nand, temporary)
        report = install(temporary, source, name, helper)
        os.replace(temporary, nand)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    report["nand"] = str(nand.resolve())
    report["transactional_install"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--name", required=True, help="new conservative ASCII 8.3 root name")
    parser.add_argument(
        "--nand",
        type=Path,
        default=deployment.WORKSPACE_ROOT / "emulator" / "windows-x86_64" / "firmware" / "h1-system.raw",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument(
        "--ecc-helper",
        type=Path,
        default=deployment.WORKSPACE_ROOT / "work" / "tools" / "jz4740-ecc-x86_64.exe",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    if not args.ecc_helper.is_file():
        raise FileNotFoundError(args.ecc_helper)

    status = deployment.api_request(args.server, "/api/status")
    was_running = bool(status.get("running"))
    if was_running:
        deployment.api_request(args.server, "/api/stop")
        deployment.wait_stopped(args.server)
    try:
        report = install_transactionally(
            args.nand.resolve(),
            args.source.resolve(),
            args.name,
            args.ecc_helper.resolve(),
        )
    finally:
        if was_running:
            deployment.api_request(args.server, "/api/start")
    report["emulator_was_running"] = was_running
    destination = args.report or deployment.SDK_ROOT / "build" / "emulator-file-install.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
