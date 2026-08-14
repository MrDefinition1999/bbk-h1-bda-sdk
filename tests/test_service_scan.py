from __future__ import annotations

import importlib.util
import struct
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "reverse" / "tools" / "scan_service_calls.py"
SPEC = importlib.util.spec_from_file_location("h1_scan_service_calls", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def instruction(opcode: int, rs: int, rt: int, immediate: int) -> bytes:
    return struct.pack("<I", opcode << 26 | rs << 21 | rt << 16 | (immediate & 0xFFFF))


class ServiceCallScanTests(unittest.TestCase):
    def test_finds_h1_gui_message_box_pattern(self) -> None:
        payload = b"".join(
            (
                instruction(0x0F, 0, 1, 0x83C0),
                instruction(0x0D, 1, 1, 4),
                instruction(0x23, 1, 1, 0),
                instruction(0x23, 1, 25, 0x2B8),
                struct.pack("<I", 25 << 21 | 31 << 11 | 0x09),
                b"\0\0\0\0",
            )
        )
        calls = MODULE.scan_payload(b"\0" * 0x88 + payload, 0x88)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["table"], "GUI")
        self.assertEqual(calls[0]["api_offset"], 0x2B8)
        self.assertEqual(calls[0]["va"], 0x83C00030)

    def test_tracks_service_table_through_h1_application_global(self) -> None:
        payload = b"".join(
            (
                instruction(0x0F, 0, 3, 0x83C0),
                instruction(0x23, 3, 3, 4),
                instruction(0x0F, 0, 1, 0x83C1),
                instruction(0x2B, 1, 3, 0x2E04),
                instruction(0x0F, 0, 3, 0x83C1),
                instruction(0x23, 3, 3, 0x2E04),
                instruction(0x23, 3, 2, 0x2B8),
                struct.pack("<I", 2 << 21 | 31 << 11 | 0x09),
                b"\0\0\0\0",
            )
        )
        calls = MODULE.scan_payload(b"\0" * 0x88 + payload, 0x88)
        self.assertEqual(
            [(call["table"], call["api_offset"]) for call in calls],
            [("GUI", 0x2B8)],
        )

    def test_markdown_keeps_static_evidence_separate_from_public_api(self) -> None:
        files = [
            {
                "path": "sample.bda",
                "payload_offset": 0x785C,
                "calls": [
                    {
                        "file_offset": 0x786C,
                        "va": 0x83C00030,
                        "table": "GUI",
                        "api_offset": 0x2B8,
                    }
                ],
            }
        ]
        report = MODULE.render_markdown(
            Path("."), files, MODULE.collections.Counter({("GUI", 0x2B8): 1})
        )
        self.assertIn("normal BDA files with calls: 1", report)
        self.assertIn("`+0x2B8`", report)
        self.assertIn("not by itself prove a function name", report)


if __name__ == "__main__":
    unittest.main()
