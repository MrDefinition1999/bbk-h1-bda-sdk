#!/usr/bin/env python3
"""List or replace one BDA in an H1 emulator NAND image."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


SDK_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SDK_ROOT.parent
H1_TOOLS = WORKSPACE_ROOT / "scripts"
if str(H1_TOOLS) not in sys.path:
    sys.path.insert(0, str(H1_TOOLS))


def load_workspace_module(name: str, path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"required H1 emulator tool is missing: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h1_ftl = load_workspace_module("h1_ftl", H1_TOOLS / "h1_ftl.py")
build_nand = load_workspace_module(
    "build_h1_system_nand", H1_TOOLS / "build_h1_system_nand.py"
)


@dataclass(frozen=True)
class FatGeometry:
    boot_offset: int
    bytes_per_sector: int
    sectors_per_cluster: int
    reserved_sectors: int
    fat_copies: int
    root_entries: int
    sectors_per_fat: int
    total_sectors: int

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    @property
    def fat_offset(self) -> int:
        return self.boot_offset + self.reserved_sectors * self.bytes_per_sector

    @property
    def root_offset(self) -> int:
        return self.fat_offset + (
            self.fat_copies * self.sectors_per_fat * self.bytes_per_sector
        )

    @property
    def root_size(self) -> int:
        return self.root_entries * 32

    @property
    def data_offset(self) -> int:
        return self.root_offset + self.root_size

    @property
    def fat_size(self) -> int:
        return self.sectors_per_fat * self.bytes_per_sector

    @property
    def data_sectors(self) -> int:
        volume_start_sector = self.boot_offset // self.bytes_per_sector
        data_start_sector = self.data_offset // self.bytes_per_sector
        return self.total_sectors - (data_start_sector - volume_start_sector)

    @property
    def data_cluster_count(self) -> int:
        return self.data_sectors // self.sectors_per_cluster

    @property
    def max_data_cluster(self) -> int:
        return self.data_cluster_count + 1

    def fat_copy_offset(self, copy_index: int) -> int:
        if copy_index < 0 or copy_index >= self.fat_copies:
            raise IndexError(copy_index)
        return self.fat_offset + copy_index * self.fat_size


@dataclass(frozen=True)
class FatEntry:
    path: str
    name: str
    attributes: int
    first_cluster: int
    size: int
    directory_entry_offset: int

    @property
    def is_directory(self) -> bool:
        return bool(self.attributes & 0x10)


class H1Fat16:
    def __init__(self, nand: Path):
        self.nand = nand.resolve()
        self.scan = h1_ftl.scan_image(self.nand)
        self.reader = build_nand.LogicalReader(self.nand, self.scan)
        self.geometry = self._read_geometry()

    def close(self) -> None:
        self.reader.close()

    def __enter__(self) -> "H1Fat16":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _read_geometry(self) -> FatGeometry:
        boot_offset = h1_ftl.DEFAULT_VOLUME_LBA * 512
        boot = self.reader.read(boot_offset, 512)
        if boot[510:512] != b"\x55\xAA" or boot[54:62].rstrip() != b"FAT16":
            raise ValueError("H1 logical volume does not contain the expected FAT16 BPB")
        total_sectors_16 = struct.unpack_from("<H", boot, 19)[0]
        total_sectors_32 = struct.unpack_from("<I", boot, 32)[0]
        geometry = FatGeometry(
            boot_offset=boot_offset,
            bytes_per_sector=struct.unpack_from("<H", boot, 11)[0],
            sectors_per_cluster=boot[13],
            reserved_sectors=struct.unpack_from("<H", boot, 14)[0],
            fat_copies=boot[16],
            root_entries=struct.unpack_from("<H", boot, 17)[0],
            sectors_per_fat=struct.unpack_from("<H", boot, 22)[0],
            total_sectors=total_sectors_16 or total_sectors_32,
        )
        if (
            geometry.bytes_per_sector != 512
            or geometry.cluster_size != 16 * 1024
            or geometry.total_sectors <= 0
            or geometry.fat_copies < 1
        ):
            raise ValueError(f"unexpected H1 FAT geometry: {geometry}")
        return geometry

    def cluster_offset(self, cluster: int) -> int:
        if cluster < 2:
            raise ValueError(f"invalid FAT data cluster {cluster}")
        return self.geometry.data_offset + (cluster - 2) * self.geometry.cluster_size

    def cluster_has_backing(self, cluster: int) -> bool:
        logical = self.cluster_offset(cluster) // h1_ftl.LOGICAL_UNIT_SIZE
        return logical in self.scan.mapping

    def fat_entry(self, cluster: int, copy_index: int = 0) -> int:
        value = self.reader.read(
            self.geometry.fat_copy_offset(copy_index) + cluster * 2,
            2,
        )
        return int.from_bytes(value, "little")

    def next_cluster(self, cluster: int) -> int:
        return self.fat_entry(cluster)

    def cluster_chain(self, first: int) -> list[int]:
        if first < 2:
            return []
        chain: list[int] = []
        seen: set[int] = set()
        cluster = first
        while 2 <= cluster < 0xFFF8:
            if cluster in seen:
                raise ValueError(f"FAT loop at cluster 0x{cluster:04X}")
            seen.add(cluster)
            chain.append(cluster)
            cluster = self.next_cluster(cluster)
            if cluster == 0xFFF7:
                raise ValueError("FAT chain reaches a bad cluster")
            if cluster in {0, 1}:
                raise ValueError("FAT chain terminates in a free/reserved cluster")
        return chain

    @staticmethod
    def _lfn_part(raw: bytes) -> tuple[int, str]:
        order = raw[0] & 0x1F
        units = raw[1:11] + raw[14:26] + raw[28:32]
        chars: list[str] = []
        for offset in range(0, len(units), 2):
            codepoint = int.from_bytes(units[offset : offset + 2], "little")
            if codepoint in {0x0000, 0xFFFF}:
                break
            chars.append(chr(codepoint))
        return order, "".join(chars)

    @staticmethod
    def _short_name(raw: bytes) -> str:
        base = raw[:8].rstrip(b" ").decode("cp936", errors="replace")
        suffix = raw[8:11].rstrip(b" ").decode("cp936", errors="replace")
        return base if not suffix else f"{base}.{suffix}"

    def _parse_directory(self, data: bytes, base_offset: int, parent: str) -> list[FatEntry]:
        output: list[FatEntry] = []
        lfn_parts: dict[int, str] = {}
        for offset in range(0, len(data), 32):
            raw = data[offset : offset + 32]
            if len(raw) != 32 or raw[0] == 0x00:
                break
            if raw[0] == 0xE5:
                lfn_parts.clear()
                continue
            attributes = raw[11]
            if attributes == 0x0F:
                order, part = self._lfn_part(raw)
                lfn_parts[order] = part
                continue
            if attributes & 0x08:
                lfn_parts.clear()
                continue
            name = "".join(lfn_parts[index] for index in sorted(lfn_parts)) if lfn_parts else self._short_name(raw)
            lfn_parts.clear()
            if name in {".", ".."}:
                continue
            first_cluster = int.from_bytes(raw[26:28], "little")
            size = int.from_bytes(raw[28:32], "little")
            path = f"{parent}/{name}" if parent else f"/{name}"
            output.append(
                FatEntry(
                    path=path,
                    name=name,
                    attributes=attributes,
                    first_cluster=first_cluster,
                    size=size,
                    directory_entry_offset=base_offset + offset,
                )
            )
        return output

    def read_chain(self, first_cluster: int, size: int | None = None) -> bytes:
        output = bytearray()
        for cluster in self.cluster_chain(first_cluster):
            output.extend(self.reader.read(self.cluster_offset(cluster), self.geometry.cluster_size))
        return bytes(output if size is None else output[:size])

    def entries(self) -> list[FatEntry]:
        output: list[FatEntry] = []
        pending: list[tuple[str, int]] = [("", 0)]
        visited: set[int] = set()
        while pending:
            parent, first_cluster = pending.pop()
            if first_cluster == 0:
                data = self.reader.read(self.geometry.root_offset, self.geometry.root_size)
                base = self.geometry.root_offset
            else:
                if first_cluster in visited:
                    continue
                visited.add(first_cluster)
                chain = self.cluster_chain(first_cluster)
                for cluster in chain:
                    block = self.reader.read(self.cluster_offset(cluster), self.geometry.cluster_size)
                    entries = self._parse_directory(block, self.cluster_offset(cluster), parent)
                    output.extend(entries)
                    pending.extend(
                        (entry.path, entry.first_cluster)
                        for entry in entries
                        if entry.is_directory and entry.first_cluster >= 2
                    )
                continue
            entries = self._parse_directory(data, base, parent)
            output.extend(entries)
            pending.extend(
                (entry.path, entry.first_cluster)
                for entry in entries
                if entry.is_directory and entry.first_cluster >= 2
            )
        return output

    def read_file(self, entry: FatEntry) -> bytes:
        if entry.is_directory:
            raise IsADirectoryError(entry.path)
        return self.read_chain(entry.first_cluster, entry.size)


def api_request(server: str, endpoint: str, timeout: float = 30.0) -> dict[str, object]:
    request = urllib.request.Request(
        server.rstrip("/") + endpoint,
        data=b"{}" if endpoint != "/api/status" else None,
        headers={"Content-Type": "application/json"},
        method="POST" if endpoint != "/api/status" else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(f"cannot reach emulator server {server}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"unexpected response from {endpoint}")
    return value


def wait_stopped(server: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not api_request(server, "/api/status", timeout=5.0).get("running"):
            return
        time.sleep(0.1)
    raise TimeoutError("QEMU did not stop before the NAND deployment timeout")


def copy_file(source_path: Path, target_path: Path) -> None:
    with source_path.open("rb") as source, target_path.open("xb") as target:
        shutil.copyfileobj(source, target, 16 * 1024 * 1024)
        target.flush()
        os.fsync(target.fileno())


def normalize_path(value: str) -> str:
    return "/" + value.replace("\\", "/").strip("/").casefold()


def encode_short_name(name: str) -> bytes:
    """Encode one conservative ASCII FAT 8.3 name for a new root entry."""
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise ValueError("FAT file name must be one root-level 8.3 name")
    parts = name.split(".")
    if len(parts) > 2 or not parts[0] or (len(parts) == 2 and not parts[1]):
        raise ValueError(f"invalid FAT 8.3 name: {name!r}")
    base = parts[0].upper()
    suffix = parts[1].upper() if len(parts) == 2 else ""
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$~!#%&-{}()@'`"
    if len(base) > 8 or len(suffix) > 3 or any(char not in allowed for char in base + suffix):
        raise ValueError(f"file name is not a conservative ASCII 8.3 name: {name!r}")
    return base.encode("ascii").ljust(8, b" ") + suffix.encode("ascii").ljust(3, b" ")


def bda_inventory(volume: H1Fat16) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for entry in volume.entries():
        if entry.is_directory or not entry.name.casefold().endswith(".bda"):
            continue
        chain = volume.cluster_chain(entry.first_cluster)
        result.append(
            {
                "path": entry.path,
                "size": entry.size,
                "clusters": len(chain),
                "capacity": len(chain) * volume.geometry.cluster_size,
            }
        )
    return sorted(result, key=lambda item: str(item["path"]).casefold())


def find_target(
    volume: H1Fat16,
    requested: str,
    required_size: int,
    *,
    allow_growth: bool = False,
) -> FatEntry:
    candidates = [
        entry
        for entry in volume.entries()
        if not entry.is_directory and entry.name.casefold().endswith(".bda")
    ]
    wanted = normalize_path(requested)
    exact = [entry for entry in candidates if normalize_path(entry.path) == wanted]
    if not exact and "/" not in requested.replace("\\", "/").strip("/"):
        exact = [entry for entry in candidates if entry.name.casefold() == requested.casefold()]
    if len(exact) != 1:
        matches = ", ".join(entry.path for entry in exact) or "none"
        raise ValueError(f"target {requested!r} did not resolve uniquely: {matches}")
    target = exact[0]
    capacity = len(volume.cluster_chain(target.first_cluster)) * volume.geometry.cluster_size
    if required_size > capacity and not allow_growth:
        raise ValueError(
            f"replacement is {required_size} bytes but {target.path} owns only {capacity} bytes"
        )
    return target


def required_cluster_count(size: int, cluster_size: int) -> int:
    if size < 0 or cluster_size <= 0:
        raise ValueError("size must be non-negative and cluster size must be positive")
    return (size + cluster_size - 1) // cluster_size


def select_free_clusters(volume: H1Fat16, count: int) -> list[int]:
    if count < 0:
        raise ValueError("free-cluster count must be non-negative")
    selected: list[int] = []
    for cluster in range(2, volume.geometry.max_data_cluster + 1):
        if all(
            volume.fat_entry(cluster, copy_index) == 0
            for copy_index in range(volume.geometry.fat_copies)
        ):
            selected.append(cluster)
            if len(selected) == count:
                return selected
    raise ValueError(
        f"FAT16 volume has only {len(selected)} mutually free clusters; {count} required"
    )


def patch_unit(units: dict[int, bytearray], volume: H1Fat16, offset: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        logical = offset // h1_ftl.LOGICAL_UNIT_SIZE
        within = offset % h1_ftl.LOGICAL_UNIT_SIZE
        count = min(len(remaining), h1_ftl.LOGICAL_UNIT_SIZE - within)
        unit = units.get(logical)
        if unit is None:
            unit = bytearray(volume.reader.read(logical * h1_ftl.LOGICAL_UNIT_SIZE, h1_ftl.LOGICAL_UNIT_SIZE))
            units[logical] = unit
        unit[within : within + count] = remaining[:count]
        remaining = remaining[count:]
        offset += count


def patch_fat_entry(
    units: dict[int, bytearray],
    volume: H1Fat16,
    cluster: int,
    value: int,
) -> None:
    encoded = int(value).to_bytes(2, "little")
    for copy_index in range(volume.geometry.fat_copies):
        patch_unit(
            units,
            volume,
            volume.geometry.fat_copy_offset(copy_index) + cluster * 2,
            encoded,
        )


def allocate_ftl_records(scan, logical_units: set[int]):
    bbt_records = [record for record in scan.records if record.kind == "bbt"]
    if len(bbt_records) != 1:
        raise ValueError(f"expected one guest BBT slot, found {len(bbt_records)}")
    allocation_start = bbt_records[0].physical_block
    free_records = iter(
        record
        for record in scan.records
        if record.kind == "free" and record.physical_block >= allocation_start
    )
    selected = {}
    newly_allocated = {}
    for logical in sorted(logical_units):
        record = scan.mapping.get(logical)
        if record is None:
            try:
                record = next(free_records)
            except StopIteration as error:
                raise ValueError(
                    f"FTL has no free physical slot for logical unit {logical}"
                ) from error
            newly_allocated[logical] = record
        selected[logical] = record
    return selected, newly_allocated


def deploy(
    nand: Path,
    replacement: Path,
    target_name: str,
    helper: Path,
    *,
    allow_growth: bool = False,
    shrink_to_fit: bool = False,
) -> dict[str, object]:
    payload = replacement.read_bytes()
    payload_sha = hashlib.sha256(payload).hexdigest().upper()
    changed: dict[int, bytearray] = {}
    with H1Fat16(nand) as volume:
        target = find_target(
            volume,
            target_name,
            len(payload),
            allow_growth=allow_growth,
        )
        original = volume.read_file(target)
        chain = volume.cluster_chain(target.first_cluster)
        original_cluster_count = len(chain)
        required_clusters = required_cluster_count(len(payload), volume.geometry.cluster_size)
        allocated: list[int] = []
        released: list[int] = []
        if required_clusters > len(chain):
            allocated = select_free_clusters(volume, required_clusters - len(chain))
            if chain:
                patch_fat_entry(changed, volume, chain[-1], allocated[0])
            else:
                patch_unit(
                    changed,
                    volume,
                    target.directory_entry_offset + 26,
                    allocated[0].to_bytes(2, "little"),
                )
            for index, cluster in enumerate(allocated):
                next_cluster = allocated[index + 1] if index + 1 < len(allocated) else 0xFFFF
                patch_fat_entry(changed, volume, cluster, next_cluster)
            chain.extend(allocated)
        elif shrink_to_fit and required_clusters < len(chain):
            released = chain[required_clusters:]
            chain = chain[:required_clusters]
            if not chain:
                raise ValueError("refusing to remove the complete BDA cluster chain")
            patch_fat_entry(changed, volume, chain[-1], 0xFFFF)
            for cluster in released:
                patch_fat_entry(changed, volume, cluster, 0)
        capacity = len(chain) * volume.geometry.cluster_size
        padded = payload + b"\x00" * (capacity - len(payload))
        for index, cluster in enumerate(chain):
            start = index * volume.geometry.cluster_size
            patch_unit(
                changed,
                volume,
                volume.cluster_offset(cluster),
                padded[start : start + volume.geometry.cluster_size],
            )
        patch_unit(
            changed,
            volume,
            target.directory_entry_offset + 28,
            len(payload).to_bytes(4, "little"),
        )
        records, new_ftl_records = allocate_ftl_records(volume.scan, set(changed))
        original_sha = hashlib.sha256(original).hexdigest().upper()
        target_path = target.path

    with nand.open("r+b", buffering=0) as output, build_nand.EccEncoder(helper) as encoder:
        for logical in sorted(changed):
            record = records[logical]
            build_nand.write_mapped_unit(
                output,
                record,
                logical,
                bytes(changed[logical]),
                1 if logical in new_ftl_records else ((record.sequence or 0) + 1) & 0xFFFF,
                encoder,
            )
        output.flush()
        os.fsync(output.fileno())

    with H1Fat16(nand) as verified:
        bad_records = [
            record
            for record in verified.scan.records
            if record.kind in {"bad", "invalid", "torn"}
        ]
        target = find_target(verified, target_path, len(payload))
        actual = verified.read_file(target)
        if actual != payload:
            raise ValueError("deployed BDA failed FAT/FTL byte-for-byte read-back")
        if bad_records:
            raise ValueError(f"deployment produced {len(bad_records)} invalid FTL records")
        generations = {
            str(logical): verified.scan.mapping[logical].sequence for logical in sorted(changed)
        }

    return {
        "nand": str(nand.resolve()),
        "replacement": str(replacement.resolve()),
        "target": target_path,
        "original_size": len(original),
        "original_sha256": original_sha,
        "replacement_size": len(payload),
        "replacement_sha256": payload_sha,
        "cluster_capacity": capacity,
        "original_clusters": original_cluster_count,
        "replacement_clusters": len(chain),
        "allocated_clusters": allocated,
        "released_clusters": released,
        "allocated_ftl_units": {
            str(logical): record.physical_block
            for logical, record in sorted(new_ftl_records.items())
        },
        "changed_logical_units": sorted(changed),
        "verified_generations": generations,
        "readback_match": True,
        "invalid_ftl_records": 0,
    }


def deploy_transactionally(
    nand: Path,
    replacement: Path,
    target_name: str,
    helper: Path,
    *,
    allow_growth: bool = False,
    shrink_to_fit: bool = False,
) -> dict[str, object]:
    original_links = nand.stat().st_nlink
    temporary = nand.with_name(nand.name + ".deploy.tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        copy_file(nand, temporary)
        report = deploy(
            temporary,
            replacement,
            target_name,
            helper,
            allow_growth=allow_growth,
            shrink_to_fit=shrink_to_fit,
        )
        os.replace(temporary, nand)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    if nand.stat().st_nlink != 1:
        raise RuntimeError("deployed emulator NAND is not a private runtime copy")
    report["nand"] = str(nand.resolve())
    report["detached_hard_link"] = original_links > 1
    report["transactional_replace"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nand",
        type=Path,
        default=WORKSPACE_ROOT / "emulator" / "windows-x86_64" / "firmware" / "h1-system.raw",
    )
    parser.add_argument("--list", action="store_true", help="list BDA files without changing NAND")
    parser.add_argument("--bda", type=Path, help="standalone H1 BDA to deploy")
    parser.add_argument("--target", default="计算器.bda", help="existing FAT path or unique file name")
    parser.add_argument(
        "--grow",
        action="store_true",
        help="extend the target FAT16 cluster chain when the replacement is larger",
    )
    parser.add_argument(
        "--shrink",
        action="store_true",
        help="release unused tail clusters when the replacement is smaller",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument(
        "--ecc-helper",
        type=Path,
        default=WORKSPACE_ROOT / "work" / "tools" / "jz4740-ecc-x86_64.exe",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    nand = args.nand.resolve()
    if args.list:
        with H1Fat16(nand) as volume:
            print(json.dumps({"nand": str(nand), "bda": bda_inventory(volume)}, ensure_ascii=False, indent=2))
        return 0
    if args.bda is None:
        parser.error("--bda is required unless --list is used")
    if not args.ecc_helper.is_file():
        raise FileNotFoundError(args.ecc_helper)

    controller_reachable = True
    try:
        status = api_request(args.server, "/api/status")
    except RuntimeError:
        # The controller is optional for an offline transactional NAND edit.
        controller_reachable = False
        status = {"running": False}
    was_running = bool(status.get("running"))
    if was_running:
        api_request(args.server, "/api/stop")
        wait_stopped(args.server)
    try:
        report = deploy_transactionally(
            nand,
            args.bda.resolve(),
            args.target,
            args.ecc_helper.resolve(),
            allow_growth=args.grow,
            shrink_to_fit=args.shrink,
        )
    finally:
        if was_running:
            api_request(args.server, "/api/start")
    report["emulator_was_running"] = was_running
    report["controller_reachable"] = controller_reachable
    report_path = args.report or SDK_ROOT / "build" / "emulator-deployment.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
