#!/usr/bin/env python3
"""Reset H1 and launch a BDA temporarily installed in a fixed dock slot."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from navigate_emulator_game_slot import (
    KEYBOARD_ENTER,
    KEYBOARD_ESCAPE,
    api,
    capture,
    press_key,
    tap,
    wait_for_boot_prompt,
    wait_for_calibration,
)


DOCK_VIDEO_SLOT = (240, 240)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    parser.add_argument("--launch-wait", type=float, default=12.0)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    status = api(args.server, "/api/status")
    api(args.server, "/api/reset" if status.get("running") else "/api/start", {})
    wait_for_calibration(args.server, args.timeout)
    wait_for_boot_prompt(args.server, args.timeout)
    time.sleep(0.5)

    press_key(args.server, KEYBOARD_ESCAPE)
    time.sleep(3.0)
    press_key(args.server, KEYBOARD_ENTER)
    time.sleep(2.0)
    press_key(args.server, KEYBOARD_ESCAPE)
    time.sleep(1.0)
    tap(args.server, *DOCK_VIDEO_SLOT)
    time.sleep(args.launch_wait)

    if args.capture:
        capture(args.server, args.capture)
    result = api(args.server, "/api/status")
    print(
        json.dumps(
            {
                "reached": "fixed-video-dock-slot",
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
