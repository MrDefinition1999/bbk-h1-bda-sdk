#!/usr/bin/env python3
"""Verify that a running H1 game keeps rendering, producing audio, and accepting input."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from capture_emulator_frame import convert_frame, encode_png


def api(server: str, endpoint: str, payload: dict[str, object] | None = None):
    request = urllib.request.Request(
        server.rstrip("/") + endpoint,
        data=None if payload is None else json.dumps(payload).encode("ascii"),
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def press_key(server: str, code: int, hold: float) -> None:
    api(server, "/api/key", {"code": code, "down": True})
    time.sleep(hold)
    api(server, "/api/key", {"code": code, "down": False})


def capture(server: str, output: Path) -> None:
    with urllib.request.urlopen(server.rstrip("/") + "/api/debug/frame", timeout=10) as response:
        packet = response.read()
    width, height, rgba = convert_frame(packet)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encode_png(width, height, rgba))


def metric(status: dict[str, object], *path: str) -> int:
    value: object = status
    for key in path:
        if not isinstance(value, dict):
            return 0
        value = value.get(key, 0)
    return int(value or 0)


def sample(status: dict[str, object], elapsed: float) -> dict[str, object]:
    return {
        "elapsed": round(elapsed, 3),
        "running": bool(status.get("running")),
        "pid": status.get("pid"),
        "uptime": status.get("uptime"),
        "frame_count": metric(status, "frame", "count"),
        "frame_sequence": metric(status, "frame", "sequence"),
        "frame_age": (status.get("frame") or {}).get("age"),
        "guest_instructions": metric(status, "performance", "guest_instructions"),
        "qemu_realtime_ms": metric(status, "performance", "qemu_realtime_ms"),
        "audio_packets": metric(status, "audio", "packets"),
        "audio_frames": metric(status, "audio", "frames"),
        "audio_sample_rate": metric(status, "audio", "sample_rate"),
        "audio_output_frames": metric(status, "audio", "diagnostics", "output_frames"),
        "audio_underruns": metric(status, "audio", "diagnostics", "underruns"),
        "audio_dma_completions": metric(
            status, "audio", "diagnostics", "dma_completions"
        ),
        "audio_dma_rearms": metric(status, "audio", "diagnostics", "dma_rearms"),
        "input_count": metric(status, "input_count"),
        "last_error": status.get("last_error"),
    }


def parse_key_sequence(value: str) -> list[int]:
    if not value.strip():
        return []
    keys = [int(item.strip(), 0) for item in value.split(",") if item.strip()]
    if any(key < 1 or key > 255 for key in keys):
        raise argparse.ArgumentTypeError("key codes must be between 1 and 255")
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--sample-interval", type=float, default=5.0)
    parser.add_argument("--key-interval", type=float, default=5.0)
    parser.add_argument("--key-hold", type=float, default=0.15)
    parser.add_argument("--key-sequence", type=parse_key_sequence, default=[])
    parser.add_argument("--require-audio", action="store_true")
    parser.add_argument("--capture-start", type=Path)
    parser.add_argument("--capture-end", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.duration <= 0 or args.sample_interval <= 0 or args.key_interval <= 0:
        parser.error("duration and intervals must be positive")

    started = time.monotonic()
    initial_status = api(args.server, "/api/status")
    if args.capture_start:
        capture(args.server, args.capture_start)
    samples = [sample(initial_status, 0.0)]
    next_sample = started + args.sample_interval
    next_key = started + args.key_interval
    key_index = 0
    deadline = started + args.duration

    while time.monotonic() < deadline:
        now = time.monotonic()
        wake = min(deadline, next_sample, next_key if args.key_sequence else deadline)
        if wake > now:
            time.sleep(wake - now)
        now = time.monotonic()
        if args.key_sequence and now >= next_key and now < deadline:
            press_key(
                args.server,
                args.key_sequence[key_index % len(args.key_sequence)],
                args.key_hold,
            )
            key_index += 1
            next_key += args.key_interval
        if now >= next_sample or now >= deadline:
            samples.append(sample(api(args.server, "/api/status"), now - started))
            next_sample += args.sample_interval

    final_status = api(args.server, "/api/status")
    final_sample = sample(final_status, time.monotonic() - started)
    if samples[-1]["elapsed"] != final_sample["elapsed"]:
        samples.append(final_sample)
    if args.capture_end:
        capture(args.server, args.capture_end)

    first = samples[0]
    last = samples[-1]
    errors: list[str] = []
    if not all(item["running"] for item in samples):
        errors.append("emulator stopped during the sample")
    pids = {item["pid"] for item in samples}
    if None in pids or len(pids) != 1:
        errors.append(f"emulator PID changed: {sorted(str(pid) for pid in pids)}")
    if any(item["last_error"] for item in samples):
        errors.append("the emulator reported last_error")
    if int(last["frame_count"]) <= int(first["frame_count"]):
        errors.append("frame count did not advance")
    if int(last["frame_sequence"]) <= int(first["frame_sequence"]):
        errors.append("frame sequence did not advance")
    if args.require_audio:
        if int(last["audio_frames"]) <= int(first["audio_frames"]):
            errors.append("audio frame count did not advance")
        if int(last["audio_output_frames"]) <= int(first["audio_output_frames"]):
            errors.append("audio output frame count did not advance")
        if int(last["audio_sample_rate"]) <= 0:
            errors.append("audio sample rate is zero")
    if int(last["audio_underruns"]) != int(first["audio_underruns"]):
        errors.append("audio underrun count increased")
    if int(last["audio_dma_completions"]) != int(last["audio_dma_rearms"]):
        errors.append("audio DMA completion/rearm counts differ")

    report = {
        "format": "h1-emulator-gameplay-stability-v1",
        "ok": not errors,
        "errors": errors,
        "server": args.server,
        "duration_seconds": args.duration,
        "sample_interval_seconds": args.sample_interval,
        "key_sequence": args.key_sequence,
        "key_presses": key_index,
        "capture_start": str(args.capture_start.resolve()) if args.capture_start else None,
        "capture_end": str(args.capture_end.resolve()) if args.capture_end else None,
        "deltas": {
            "frames": int(last["frame_count"]) - int(first["frame_count"]),
            "frame_sequence": int(last["frame_sequence"])
            - int(first["frame_sequence"]),
            "guest_instructions": int(last["guest_instructions"])
            - int(first["guest_instructions"]),
            "qemu_realtime_ms": int(last["qemu_realtime_ms"])
            - int(first["qemu_realtime_ms"]),
            "audio_frames": int(last["audio_frames"]) - int(first["audio_frames"]),
            "audio_output_frames": int(last["audio_output_frames"])
            - int(first["audio_output_frames"]),
            "audio_underruns": int(last["audio_underruns"])
            - int(first["audio_underruns"]),
            "input_count": int(last["input_count"]) - int(first["input_count"]),
        },
        "samples": samples,
        "stderr_tail": final_status.get("stderr_tail", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
