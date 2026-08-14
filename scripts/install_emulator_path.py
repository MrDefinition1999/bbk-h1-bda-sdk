#!/usr/bin/env python3
"""Transactionally add one file below a new or explicitly reused H1 directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from datetime import datetime
from pathlib import Path

import deploy_emulator_bda as deployment


def dos_timestamp(now: datetime) -> tuple[int, int]:
    year = max(1980, min(2107, now.year))
    date = ((year - 1980) << 9) | (now.month << 5) | now.day
    stamp = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    return date, stamp


def lfn_checksum(short_name: bytes) -> int:
    if len(short_name) != 11:
        raise ValueError("FAT short name must be exactly 11 bytes")
    checksum = 0
    for value in short_name:
        checksum = (((checksum & 1) << 7) | (checksum >> 1))
        checksum = (checksum + value) & 0xFF
    return checksum


def one_lfn_entry(long_name: str, short_name: bytes) -> bytes:
    encoded = long_name.encode("utf-16le")
    units = [int.from_bytes(encoded[index : index + 2], "little") for index in range(0, len(encoded), 2)]
    if not units or len(units) > 12:
        raise ValueError("this installer supports one non-empty FAT LFN entry of at most 12 UTF-16 units")
    units.append(0)
    units.extend([0xFFFF] * (13 - len(units)))

    raw = bytearray(32)
    raw[0] = 0x41
    raw[11] = 0x0F
    raw[12] = 0
    raw[13] = lfn_checksum(short_name)
    raw[26:28] = b"\0\0"
    slots = ((1, 5), (14, 6), (28, 2))
    cursor = 0
    for offset, count in slots:
        for index in range(count):
            raw[offset + index * 2 : offset + index * 2 + 2] = units[cursor].to_bytes(2, "little")
            cursor += 1
    return bytes(raw)


def short_entry(
    short_name: bytes,
    attributes: int,
    first_cluster: int,
    size: int,
    date: int,
    stamp: int,
) -> bytes:
    if len(short_name) != 11:
        raise ValueError("FAT short name must be exactly 11 bytes")
    raw = bytearray(32)
    raw[:11] = short_name
    raw[11] = attributes
    struct.pack_into("<H", raw, 14, stamp)
    struct.pack_into("<H", raw, 16, date)
    struct.pack_into("<H", raw, 22, stamp)
    struct.pack_into("<H", raw, 24, date)
    struct.pack_into("<H", raw, 26, first_cluster)
    struct.pack_into("<I", raw, 28, size)
    return bytes(raw)


def free_directory_slots(
    volume: deployment.H1Fat16,
    directory: deployment.FatEntry | None,
    count: int,
) -> int:
    if count <= 0 or (directory is not None and not directory.is_directory):
        raise ValueError("a directory and a positive slot count are required")
    if directory is None:
        blocks = ((volume.geometry.root_offset, volume.geometry.root_size),)
    else:
        blocks = tuple(
            (volume.cluster_offset(cluster), volume.geometry.cluster_size)
            for cluster in volume.cluster_chain(directory.first_cluster)
        )
    for base_offset, size in blocks:
        data = volume.reader.read(base_offset, size)
        run_start = -1
        run_count = 0
        for offset in range(0, len(data), 32):
            if data[offset] in {0x00, 0xE5}:
                if run_count == 0:
                    run_start = offset
                run_count += 1
                if run_count == count:
                    return base_offset + run_start
            else:
                run_start = -1
                run_count = 0
    path = "/" if directory is None else directory.path
    raise ValueError(f"directory {path} has no {count} contiguous free entries")


def install(
    nand: Path,
    source: Path,
    parent_path: str,
    directory_name: str,
    file_name: str,
    short_alias: str,
    helper: Path,
    reuse_directory: bool = False,
) -> dict[str, object]:
    payload = source.read_bytes()
    if not payload:
        raise ValueError("refusing to install an empty H1 data file")
    directory_short = deployment.encode_short_name(directory_name)
    file_short = deployment.encode_short_name(short_alias)
    file_lfn = one_lfn_entry(file_name, file_short)
    target_directory = f"{parent_path.rstrip('/')}/{directory_name}"
    target_path = f"{target_directory}/{file_name}"
    changed: dict[int, bytearray] = {}

    with deployment.H1Fat16(nand) as volume:
        entries = volume.entries()
        target_directories = [
            entry
            for entry in entries
            if entry.is_directory
            and deployment.normalize_path(entry.path)
            == deployment.normalize_path(target_directory)
        ]
        if any(
            deployment.normalize_path(entry.path)
            == deployment.normalize_path(target_path)
            for entry in entries
        ):
            raise FileExistsError(f"{target_path} already exists in the H1 volume")
        if target_directories:
            if not reuse_directory:
                raise FileExistsError(
                    f"{target_directory} already exists in the H1 volume"
                )
            if len(target_directories) != 1:
                raise ValueError(
                    f"{target_directory} did not resolve uniquely"
                )
            directory = target_directories[0]
            directory_cluster = directory.first_cluster
            file_slot = free_directory_slots(volume, directory, 2)
            parent = None
            parent_slot = None
        else:
            if reuse_directory:
                raise FileNotFoundError(
                    f"{target_directory} does not exist in the H1 volume"
                )
            if deployment.normalize_path(parent_path) == "/":
                parent = None
            else:
                parents = [
                    entry
                    for entry in entries
                    if entry.is_directory
                    and deployment.normalize_path(entry.path)
                    == deployment.normalize_path(parent_path)
                ]
                if len(parents) != 1:
                    raise ValueError(
                        f"parent {parent_path!r} did not resolve uniquely"
                    )
                parent = parents[0]
            parent_slot = free_directory_slots(volume, parent, 1)
            file_slot = None

        file_cluster_count = deployment.required_cluster_count(len(payload), volume.geometry.cluster_size)
        allocated = deployment.select_free_clusters(
            volume,
            file_cluster_count + (0 if target_directories else 1),
        )
        if target_directories:
            file_chain = allocated
        else:
            directory_cluster = allocated[0]
            file_chain = allocated[1:]
            deployment.patch_fat_entry(
                changed, volume, directory_cluster, 0xFFFF
            )
        for index, cluster in enumerate(file_chain):
            next_cluster = file_chain[index + 1] if index + 1 < len(file_chain) else 0xFFFF
            deployment.patch_fat_entry(changed, volume, cluster, next_cluster)

        date, stamp = dos_timestamp(datetime.now())
        file_entry = short_entry(
            file_short, 0x20, file_chain[0], len(payload), date, stamp
        )
        if target_directories:
            assert file_slot is not None
            deployment.patch_unit(
                changed, volume, file_slot, file_lfn + file_entry
            )
        else:
            directory_data = bytearray(volume.geometry.cluster_size)
            directory_data[0:32] = short_entry(
                b".          ", 0x10, directory_cluster, 0, date, stamp
            )
            parent_cluster = 0 if parent is None else parent.first_cluster
            directory_data[32:64] = short_entry(
                b"..         ", 0x10, parent_cluster, 0, date, stamp
            )
            directory_data[64:96] = file_lfn
            directory_data[96:128] = file_entry
            deployment.patch_unit(
                changed,
                volume,
                volume.cluster_offset(directory_cluster),
                directory_data,
            )

        capacity = len(file_chain) * volume.geometry.cluster_size
        padded = payload + bytes(capacity - len(payload))
        for index, cluster in enumerate(file_chain):
            start = index * volume.geometry.cluster_size
            deployment.patch_unit(
                changed,
                volume,
                volume.cluster_offset(cluster),
                padded[start : start + volume.geometry.cluster_size],
            )
        if not target_directories:
            assert parent_slot is not None
            deployment.patch_unit(
                changed,
                volume,
                parent_slot,
                short_entry(
                    directory_short, 0x10, directory_cluster, 0, date, stamp
                ),
            )
        records, new_ftl_records = deployment.allocate_ftl_records(volume.scan, set(changed))

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
            if not entry.is_directory
            and deployment.normalize_path(entry.path) == deployment.normalize_path(target_path)
        ]
        if len(matches) != 1:
            raise ValueError(f"installed {target_path} did not resolve uniquely")
        if verified.read_file(matches[0]) != payload:
            raise ValueError(f"installed {target_path} failed byte-for-byte read-back")
        bad_records = [
            record for record in verified.scan.records if record.kind in {"bad", "invalid", "torn"}
        ]
        if bad_records:
            raise ValueError(f"installation produced {len(bad_records)} invalid FTL records")
        generations = {
            str(logical): verified.scan.mapping[logical].sequence for logical in sorted(changed)
        }

    return {
        "nand": str(nand.resolve()),
        "source": str(source.resolve()),
        "target": target_path,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "directory_cluster": directory_cluster,
        "reused_directory": bool(target_directories),
        "file_clusters": len(file_chain),
        "cluster_capacity": capacity,
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
    nand: Path,
    source: Path,
    parent_path: str,
    directory_name: str,
    file_name: str,
    short_alias: str,
    helper: Path,
    reuse_directory: bool = False,
) -> dict[str, object]:
    temporary = nand.with_name(nand.name + ".path-install.tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        deployment.copy_file(nand, temporary)
        report = install(
            temporary,
            source,
            parent_path,
            directory_name,
            file_name,
            short_alias,
            helper,
            reuse_directory,
        )
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
    parser.add_argument("--parent", default="/应用/数据")
    parser.add_argument("--directory", default="CS15LITE")
    parser.add_argument("--name", default="CS15.C15PAK")
    parser.add_argument("--short-alias", default="CS15~1.C15")
    parser.add_argument(
        "--reuse-directory",
        action="store_true",
        help="install into an existing directory and refuse if the file exists",
    )
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

    controller_reachable = True
    try:
        status = deployment.api_request(args.server, "/api/status")
    except RuntimeError:
        # Offline NAND installation is valid when the controller was never
        # started.  The transactional writer still verifies the full result.
        controller_reachable = False
        status = {"running": False}
    was_running = bool(status.get("running"))
    if was_running:
        deployment.api_request(args.server, "/api/stop")
        deployment.wait_stopped(args.server)
    try:
        report = install_transactionally(
            args.nand.resolve(),
            args.source.resolve(),
            args.parent,
            args.directory,
            args.name,
            args.short_alias,
            args.ecc_helper.resolve(),
            args.reuse_directory,
        )
    finally:
        if was_running:
            deployment.api_request(args.server, "/api/start")
    report["emulator_was_running"] = was_running
    report["controller_reachable"] = controller_reachable
    destination = args.report or deployment.SDK_ROOT / "build" / "emulator-path-install.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
