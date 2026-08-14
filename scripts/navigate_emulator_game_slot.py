#!/usr/bin/env python3
"""Reset H1 and navigate to the fixed final game slot without image matching."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from capture_emulator_frame import convert_frame, encode_png


KEYBOARD_ENTER = 25
KEYBOARD_ESCAPE = 24
ACTION_CONFIRM = 39
ACTION_BACK = 41
CATEGORY_BUTTON = (360, 14)
OTHER_CATEGORY = (358, 166)
GAME_SLOT = (305, 51)
SWIPE_X = (420, 380, 340, 300, 260, 220, 180, 140, 100, 60)
SWIPE_Y = 150
MIN_PROMPT_UPTIME = 15.0
READY_CALIBRATION_STATES = {"complete", "not-required"}


def api(server: str, endpoint: str, payload: dict[str, object] | None = None):
    request = urllib.request.Request(
        server.rstrip("/") + endpoint,
        data=None if payload is None else json.dumps(payload).encode("ascii"),
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def wait_for_calibration(server: str, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        last = api(server, "/api/status")
        if (
            last.get("running")
            and last.get("calibration_status") in READY_CALIBRATION_STATES
        ):
            return last
        time.sleep(0.25)
    raise TimeoutError(f"H1 calibration did not complete: {last}")


def wait_for_boot_prompt(server: str, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        last = api(server, "/api/status")
        frame = last.get("frame") or {}
        if (
            float(last.get("uptime") or 0) >= MIN_PROMPT_UPTIME
            and int(frame.get("count") or 0) >= 1
        ):
            return last
        time.sleep(0.25)
    raise TimeoutError(f"H1 boot prompt did not stabilize: {last}")


def press_key(server: str, code: int) -> None:
    api(server, "/api/key", {"code": code, "down": True})
    time.sleep(0.12)
    api(server, "/api/key", {"code": code, "down": False})


def tap(server: str, x: int, y: int) -> None:
    api(server, "/api/touch", {"x": x, "y": y, "down": True})
    time.sleep(0.22)
    api(server, "/api/touch", {"x": x, "y": y, "down": False})


def swipe_left(server: str) -> None:
    api(server, "/api/touch", {"x": SWIPE_X[0], "y": SWIPE_Y, "down": True})
    time.sleep(0.24)
    for x in SWIPE_X[1:]:
        api(server, "/api/touch", {"x": x, "y": SWIPE_Y, "down": True})
        time.sleep(0.065)
    api(server, "/api/touch", {"x": SWIPE_X[-1], "y": SWIPE_Y, "down": False})


def swipe_right(server: str) -> None:
    api(server, "/api/touch", {"x": SWIPE_X[-1], "y": SWIPE_Y, "down": True})
    time.sleep(0.24)
    for x in reversed(SWIPE_X[:-1]):
        api(server, "/api/touch", {"x": x, "y": SWIPE_Y, "down": True})
        time.sleep(0.065)
    api(server, "/api/touch", {"x": SWIPE_X[0], "y": SWIPE_Y, "down": False})


def capture(server: str, output: Path) -> None:
    with urllib.request.urlopen(server.rstrip("/") + "/api/debug/frame", timeout=10) as response:
        packet = response.read()
    width, height, rgba = convert_frame(packet)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encode_png(width, height, rgba))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument(
        "--page-swipes",
        type=int,
        default=1,
        help="number of left swipes from the factory page to the custom-game page",
    )
    parser.add_argument("--slot-x", type=int, default=GAME_SLOT[0])
    parser.add_argument("--slot-y", type=int, default=GAME_SLOT[1])
    parser.add_argument(
        "--confirm-after-launch",
        action="store_true",
        help=(
            "press the permanent confirm key five seconds after tapping; "
            "use only for ports that require it because native BDA slots may "
            "launch on the touch itself"
        ),
    )
    parser.add_argument(
        "--launch-wait",
        type=float,
        default=30.0,
        help="seconds to wait for the NAND-loaded game after starting it",
    )
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    if args.page_swipes < 0:
        parser.error("--page-swipes must not be negative")

    status = api(args.server, "/api/status")
    if not args.no_reset:
        api(args.server, "/api/reset" if status.get("running") else "/api/start", {})
    wait_for_calibration(args.server, args.timeout)
    wait_for_boot_prompt(args.server, args.timeout)
    time.sleep(0.5)

    # Cancel the stable clock-change prompt, accept the restored desktop's
    # low-disk warning, then leave any Time application fallback.
    press_key(args.server, KEYBOARD_ESCAPE)
    time.sleep(3.0)
    press_key(args.server, KEYBOARD_ENTER)
    time.sleep(2.0)
    press_key(args.server, KEYBOARD_ESCAPE)
    time.sleep(1.0)
    tap(args.server, *CATEGORY_BUTTON)
    time.sleep(0.7)
    tap(args.server, *OTHER_CATEGORY)
    time.sleep(1.2)
    for _ in range(args.page_swipes):
        swipe_left(args.server)
        time.sleep(0.8)
    time.sleep(1.2)

    if args.launch:
        tap(args.server, args.slot_x, args.slot_y)
        if args.confirm_after_launch:
            time.sleep(5.0)
            press_key(args.server, ACTION_CONFIRM)
        time.sleep(args.launch_wait)
    if args.capture:
        capture(args.server, args.capture)

    result = api(args.server, "/api/status")
    print(
        json.dumps(
            {
                "reached": "custom-game-page",
                "launched": args.launch,
                "capture": str(args.capture.resolve()) if args.capture else None,
                "pid": result.get("pid"),
                "uptime": result.get("uptime"),
                "input_count": result.get("input_count"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
