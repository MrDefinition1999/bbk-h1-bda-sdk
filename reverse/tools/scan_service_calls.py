from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from h1_bda.header import MAGIC, decode_header


ENTRY_VA = 0x83C00020
NORMAL_PAYLOAD_OFFSET = 0x785C
TABLE_SLOTS = {
    0x83C00004: "GUI",
    0x83C00008: "FS",
    0x83C0000C: "SYS",
    0x83C00010: "MEM",
    0x83C00014: "RES",
}


@dataclass(frozen=True)
class TableValue:
    name: str


@dataclass(frozen=True)
class ApiValue:
    table: str
    offset: int


def _signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _decode_header(path: Path, data: bytes) -> tuple[int, int]:
    decoded = decode_header(data)
    words = struct.unpack_from("<11I", decoded)
    if words[0] != MAGIC:
        raise ValueError(f"{path}: invalid H1 BDA magic")
    payload_offset = words[5]
    if payload_offset < 0x88 or payload_offset >= len(data):
        raise ValueError(f"{path}: invalid payload offset 0x{payload_offset:x}")
    return payload_offset, words[3]


def scan_payload(data: bytes, payload_offset: int) -> list[dict[str, int | str]]:
    state: list[int | TableValue | ApiValue | None] = [None] * 32
    state[0] = 0
    memory: dict[int, TableValue | ApiValue] = {}
    calls: list[dict[str, int | str]] = []

    for file_offset in range(payload_offset, len(data) - 3, 4):
        word = struct.unpack_from("<I", data, file_offset)[0]
        opcode = word >> 26
        rs = (word >> 21) & 31
        rt = (word >> 16) & 31
        rd = (word >> 11) & 31
        immediate = word & 0xFFFF
        value: int | TableValue | ApiValue | None

        if opcode == 0x0F:  # lui
            state[rt] = immediate << 16
        elif opcode == 0x0D:  # ori
            source = state[rs]
            state[rt] = (source | immediate) & 0xFFFFFFFF if isinstance(source, int) else None
        elif opcode == 0x09:  # addiu
            source = state[rs]
            state[rt] = (source + _signed16(immediate)) & 0xFFFFFFFF if isinstance(source, int) else None
        elif opcode == 0x23:  # lw
            source = state[rs]
            if isinstance(source, int):
                address = (source + _signed16(immediate)) & 0xFFFFFFFF
                name = TABLE_SLOTS.get(address)
                value = TableValue(name) if name else memory.get(address)
            elif isinstance(source, TableValue) and immediate % 4 == 0:
                value = ApiValue(source.name, immediate)
            else:
                value = None
            state[rt] = value
        elif opcode == 0x2B:  # sw
            base = state[rs]
            stored = state[rt]
            if isinstance(base, int):
                address = (base + _signed16(immediate)) & 0xFFFFFFFF
                if isinstance(stored, (TableValue, ApiValue)):
                    memory[address] = stored
                else:
                    memory.pop(address, None)
        elif opcode == 0:
            function = word & 0x3F
            if function == 0x09:  # jalr
                target = state[rs]
                if isinstance(target, ApiValue):
                    calls.append(
                        {
                            "file_offset": file_offset,
                            "va": ENTRY_VA + file_offset - payload_offset,
                            "table": target.table,
                            "api_offset": target.offset,
                        }
                    )
                state[rs] = None
            elif function in (0x21, 0x25):  # addu/or; compilers use these for move
                left = state[rs]
                right = state[rt]
                if rs == 0:
                    state[rd] = right
                elif rt == 0:
                    state[rd] = left
                else:
                    state[rd] = None
            elif function == 0x08:  # jr
                state = [None] * 32
                state[0] = 0
            elif rd:
                state[rd] = None
        elif opcode in (0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            state = [None] * 32
            state[0] = 0
        else:
            # Clear the common destination register for instructions not modeled above.
            if opcode not in (0x28, 0x29, 0x2B) and rt:
                state[rt] = None

    return calls


def scan_file(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    payload_offset, category = _decode_header(path, data)
    calls = scan_payload(data, payload_offset)
    return {
        "path": str(path),
        "category": category,
        "payload_offset": payload_offset,
        "calls": calls,
    }


def render_markdown(
    root: Path,
    files: list[dict[str, object]],
    totals: collections.Counter[tuple[str, int]],
) -> str:
    apps_by_api: dict[tuple[str, int], set[str]] = collections.defaultdict(set)
    samples: dict[tuple[str, int], list[tuple[str, int]]] = collections.defaultdict(list)
    for report in files:
        path = str(report["path"])
        seen: set[tuple[str, int]] = set()
        for call in report["calls"]:
            key = (str(call["table"]), int(call["api_offset"]))
            seen.add(key)
            if len(samples[key]) < 3:
                samples[key].append((path, int(call["va"])))
        for key in seen:
            apps_by_api[key].add(path)

    lines = [
        "# H1 Native BDA Service-Call Inventory",
        "",
        "This report is generated by `reverse/tools/scan_service_calls.py` from",
        "the H1 V1.41 SD-recovery application's own MIPS code. It tracks each",
        "service pointer through the normal BDA entry's global table copies and",
        "records the table-relative function loaded immediately before `jalr`.",
        "",
        f"- scan root: `{root}`",
        f"- normal BDA files with calls: {len(files)}",
        f"- admitted payload offset: `0x{NORMAL_PAYLOAD_OFFSET:X}`",
        "- runtime entry: `0x83C00020`",
        "- excluded layouts: `system recovery` (`0x88`) and `system upgrade`",
        "  (`0xA90`); neither uses the normal application loader contract",
        "",
        "A call count proves that an H1 application uses a table offset. It does",
        "not by itself prove a function name, signature, return contract, or safe",
        "lifecycle. Those require H1 firmware analysis and an independent dynamic",
        "probe before the API can enter `sdk/include/`.",
        "",
    ]

    for table in TABLE_SLOTS.values():
        entries = [
            (offset, count)
            for (entry_table, offset), count in sorted(totals.items())
            if entry_table == table
        ]
        lines.extend(
            [
                f"## {table} table",
                "",
                f"Distinct offsets: {len(entries)}; observed calls: "
                f"{sum(count for _offset, count in entries)}.",
                "",
                "| Offset | Calls | BDA files | First H1 call site |",
                "| ---: | ---: | ---: | --- |",
            ]
        )
        for offset, count in entries:
            sample_path, sample_va = samples[(table, offset)][0]
            try:
                display_path = str(Path(sample_path).relative_to(root))
            except ValueError:
                display_path = sample_path
            lines.append(
                f"| `+0x{offset:03X}` | {count} | "
                f"{len(apps_by_api[(table, offset)])} | "
                f"`0x{sample_va:08X}` in `{display_path}` |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan H1 BDA service-table calls")
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--all-layouts",
        action="store_true",
        help="include recovery/upgrade layouts in counts (their VA fields are not normal-app VAs)",
    )
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    files: list[dict[str, object]] = []
    totals: collections.Counter[tuple[str, int]] = collections.Counter()
    for path in sorted(args.root.rglob("*.bda")):
        try:
            report = scan_file(path)
        except ValueError:
            continue
        if not args.all_layouts and report["payload_offset"] != NORMAL_PAYLOAD_OFFSET:
            continue
        calls = report["calls"]
        if not calls:
            continue
        files.append(report)
        totals.update((str(call["table"]), int(call["api_offset"])) for call in calls)

    summary = [
        {"table": table, "api_offset": offset, "count": count}
        for (table, offset), count in sorted(totals.items())
    ]
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(
            render_markdown(args.root.resolve(), files, totals),
            encoding="utf-8",
            newline="\n",
        )
    if args.json:
        print(json.dumps({"summary": summary, "files": files}, ensure_ascii=False, indent=2))
        return

    print(f"files_with_calls={len(files)}")
    for item in summary:
        print(f"{item['table']}+0x{item['api_offset']:03x} {item['count']}")


if __name__ == "__main__":
    main()
