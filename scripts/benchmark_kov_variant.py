#!/usr/bin/env python3
"""Deploy and measure one emulator-only KOV performance variant."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


SDK_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SDK_ROOT.parent
DEPLOY = Path(__file__).with_name("deploy_emulator_bda.py")
NAVIGATE = Path(__file__).with_name("navigate_emulator_game_slot.py")
LLVM_NM = WORKSPACE_ROOT / "work/tools/msys64/clangarm64/bin/llvm-nm.exe"
COUNTER_NAME = "kov_perf_logic_frames"
KOV_SLOT = (305, 51)


def api(server: str, endpoint: str, payload: dict[str, object] | None = None):
    request = urllib.request.Request(
        server.rstrip("/") + endpoint,
        data=None if payload is None else json.dumps(payload).encode("ascii"),
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def symbol_address(elf: Path, name: str) -> int:
    completed = subprocess.run(
        [str(LLVM_NM), "-n", str(elf)],
        check=True,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[-1] == name:
            return int(fields[0], 16)
    raise RuntimeError(f"symbol {name!r} is missing from {elf}")


def read_counters(server: str, physical_address: int) -> tuple[int, int]:
    result = api(
        server,
        f"/api/debug/memory?address=0x{physical_address:08x}&count=2",
    )
    values = re.findall(r"0x([0-9a-fA-F]{8})", str(result.get("memory", "")))
    if len(values) < 2:
        raise RuntimeError("KOV counters are not mapped")
    return int(values[-2], 16), int(values[-1], 16)


def tap(server: str, x: int, y: int) -> None:
    api(server, "/api/touch", {"x": x, "y": y, "down": True})
    time.sleep(0.22)
    api(server, "/api/touch", {"x": x, "y": y, "down": False})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("bda", type=Path)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument("--warmup", type=float, default=35.0)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument(
        "--start-frame",
        type=int,
        help="align measurement to this logical frame instead of wall-time warmup",
    )
    parser.add_argument(
        "--frame-count",
        type=int,
        help="measure this many logical frames instead of a fixed duration",
    )
    args = parser.parse_args()
    if args.warmup < 0 or args.duration <= 0:
        parser.error("warmup must be nonnegative and duration must be positive")
    if (args.start_frame is None) != (args.frame_count is None):
        parser.error("--start-frame and --frame-count must be used together")
    if args.start_frame is not None and (
        args.start_frame < 1 or args.frame_count is None or args.frame_count < 1
    ):
        parser.error("aligned frame values must be positive")

    bda = args.bda.resolve()
    elf = args.elf.resolve()
    if not bda.is_file() or not elf.is_file() or not LLVM_NM.is_file():
        raise FileNotFoundError("BDA, ELF, or llvm-nm input is missing")
    report = WORKSPACE_ROOT / "work/tmp" / f"kov-ab-{args.name}-deployment.json"
    capture = WORKSPACE_ROOT / "work/tmp" / f"kov-ab-{args.name}-page.png"
    subprocess.run(
        [
            sys.executable,
            str(DEPLOY),
            "--bda",
            str(bda),
            "--target",
            "H1KOVPlus.bda",
            "--report",
            str(report),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(NAVIGATE),
            "--page-swipes",
            "1",
            "--capture",
            str(capture),
        ],
        check=True,
    )
    tap(args.server, *KOV_SLOT)

    counter_va = symbol_address(elf, COUNTER_NAME)
    counter_pa = counter_va & 0x1FFFFFFF
    deadline = time.monotonic() + max(args.warmup, 20.0)
    first_seen = 0.0
    while time.monotonic() < deadline:
        try:
            logic, rendered = read_counters(args.server, counter_pa)
            if logic > 0 and rendered > 0:
                first_seen = time.monotonic()
                break
        except (OSError, RuntimeError):
            pass
        time.sleep(0.5)
    if first_seen == 0.0:
        raise RuntimeError("KOV did not launch or expose its counters")
    if args.start_frame is None:
        remaining_warmup = args.warmup - (time.monotonic() - first_seen)
        if remaining_warmup > 0:
            time.sleep(remaining_warmup)
    else:
        alignment_deadline = time.monotonic() + 180.0
        while logic < args.start_frame and time.monotonic() < alignment_deadline:
            time.sleep(0.05)
            logic, rendered = read_counters(args.server, counter_pa)
        if logic < args.start_frame:
            raise RuntimeError("KOV did not reach the aligned start frame")

    initial_status = api(args.server, "/api/status")
    initial_logic, initial_rendered = read_counters(args.server, counter_pa)
    started = time.monotonic()
    if args.frame_count is None:
        time.sleep(args.duration)
    else:
        target_logic = initial_logic + args.frame_count
        measurement_timeout = max(180.0, args.frame_count / 30.0 + 60.0)
        measurement_deadline = time.monotonic() + measurement_timeout
        while logic < target_logic and time.monotonic() < measurement_deadline:
            time.sleep(0.05)
            logic, rendered = read_counters(args.server, counter_pa)
        if logic < target_logic:
            raise RuntimeError("KOV did not finish the aligned frame interval")
    elapsed = time.monotonic() - started
    final_status = api(args.server, "/api/status")
    final_logic, final_rendered = read_counters(args.server, counter_pa)
    audio = (final_status.get("audio") or {}).get("diagnostics") or {}
    result = {
        "name": args.name,
        "elapsed_s": round(elapsed, 3),
        "logic_frames": final_logic - initial_logic,
        "rendered_frames": final_rendered - initial_rendered,
        "logic_fps": round((final_logic - initial_logic) / elapsed, 3),
        "rendered_fps": round((final_rendered - initial_rendered) / elapsed, 3),
        "guest_instructions": int(
            (final_status.get("performance") or {}).get("guest_instructions") or 0
        )
        - int((initial_status.get("performance") or {}).get("guest_instructions") or 0),
        "underruns": int(audio.get("underruns") or 0),
        "overruns": int(audio.get("overruns") or 0),
        "pid": initial_status.get("pid"),
        "pid_stable": bool(
            initial_status.get("running")
            and final_status.get("running")
            and initial_status.get("pid") == final_status.get("pid")
        ),
        "counter_va": f"0x{counter_va:08x}",
        "counter_pa": f"0x{counter_pa:08x}",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
