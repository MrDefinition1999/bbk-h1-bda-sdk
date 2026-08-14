from __future__ import annotations

import importlib.util
import re
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = WORKSPACE_ROOT / "emulator/windows-x86_64/h1_emulator.py"
FRONTEND_HTML = WORKSPACE_ROOT / "emulator/windows-x86_64/web/index.html"


def load_frontend():
    spec = importlib.util.spec_from_file_location("h1_emulator_frontend", FRONTEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_runtime(frontend, touch_profile: str):
    return frontend.H1Runtime(
        qemu=Path("qemu-system-mipsel.exe"),
        kernel=Path("project.bin"),
        nand=Path("h1-system.raw"),
        a320_asset_dir=None,
        dll_dirs=[],
        touch_profile=touch_profile,
    )


class CalibrationFrameTests(unittest.TestCase):
    def test_each_real_target_is_detected_from_rgba_frame(self) -> None:
        frontend = load_frontend()
        header = struct.Struct("<4sIIIII")
        for touch_profile in frontend.TOUCH_PROFILES:
            runtime = make_runtime(frontend, touch_profile)
            for x, y, _raw_x, _raw_y in runtime.calibration_points:
                pixels = bytearray(frontend.FRAME_BYTES)
                for offset in range(6):
                    pixel = y * frontend.FRAME_STRIDE + (x + offset) * 4
                    pixels[pixel : pixel + 4] = bytes((0x68, 0xB0, 0xF0, 0xFF))
                packet = header.pack(
                    b"H1FR",
                    1,
                    frontend.FRAME_WIDTH,
                    frontend.FRAME_HEIGHT,
                    frontend.FRAME_STRIDE,
                    frontend.FRAME_FORMAT_RGBA8888,
                ) + pixels
                self.assertEqual(
                    runtime._visible_calibration_point(packet)[:2],
                    (x, y),
                )

    def test_non_calibration_frame_has_no_target(self) -> None:
        frontend = load_frontend()
        runtime = make_runtime(frontend, "v1")
        packet = struct.pack(
            "<4sIIIII",
            b"H1FR",
            1,
            frontend.FRAME_WIDTH,
            frontend.FRAME_HEIGHT,
            frontend.FRAME_STRIDE,
            frontend.FRAME_FORMAT_RGBA8888,
        ) + bytes(frontend.FRAME_BYTES)
        self.assertIsNone(
            runtime._visible_calibration_point(packet)
        )


class FrontendConfigurationTests(unittest.TestCase):
    def test_retired_a320_asset_bridge_is_opt_in(self) -> None:
        frontend = load_frontend()
        with mock.patch.object(
            sys,
            "argv",
            ["h1_emulator.py", "--no-start", "--no-browser"],
        ):
            args = frontend.parse_args()
        self.assertIsNone(args.a320_asset_dir)
        runtime = frontend.H1Runtime(
            qemu=args.qemu,
            kernel=args.kernel,
            nand=args.nand,
            a320_asset_dir=args.a320_asset_dir,
            dll_dirs=[],
        )
        command = runtime._build_command(41001, 41002, 41003)
        self.assertNotIn("a320-asset-dir", " ".join(command))

    def test_six_permanent_keys_and_full_keyboard_drawer_are_present(self) -> None:
        html = FRONTEND_HTML.read_text(encoding="utf-8")
        permanent = re.findall(
            r'class="[^"]*device-key[^"]*key-button[^"]*"', html
        )
        drawer = re.findall(
            r'class="[^"]*keyboard-key[^"]*key-button[^"]*"', html
        )
        self.assertEqual(len(permanent), 6)
        self.assertEqual(len(drawer), 38)
        self.assertIn('id="keyboardToggle"', html)
        self.assertIn('id="keyboardDrawer"', html)
        self.assertIn("keyboardToggle.onclick", html)


if __name__ == "__main__":
    unittest.main()
