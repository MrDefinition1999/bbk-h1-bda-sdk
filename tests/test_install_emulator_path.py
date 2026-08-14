from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SDK_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SDK_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "h1_install_emulator_path_test",
    SCRIPT_DIR / "install_emulator_path.py",
)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class InstallEmulatorPathTests(unittest.TestCase):
    def test_root_directory_slot_is_supported(self) -> None:
        geometry = type("Geometry", (), {"root_offset": 4096, "root_size": 96})()
        reader = type(
            "Reader",
            (),
            {"read": lambda _self, offset, size: b"X" * 32 + b"\xE5" + b"\0" * 63},
        )()
        volume = type("Volume", (), {"geometry": geometry, "reader": reader})()
        self.assertEqual(installer.free_directory_slots(volume, None, 1), 4096 + 32)

    def test_single_lfn_entry_round_trips(self) -> None:
        short_name = installer.deployment.encode_short_name("H1GAME~1.DAT")
        lfn = installer.one_lfn_entry("H1GAME.DAT", short_name)
        short = installer.short_entry(short_name, 0x20, 123, 456, 0, 0)
        parser = object.__new__(installer.deployment.H1Fat16)
        entries = parser._parse_directory(
            lfn + short + bytes(32), 1000, "/应用/数据/H1SDK"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "H1GAME.DAT")
        self.assertEqual(entries[0].first_cluster, 123)
        self.assertEqual(entries[0].size, 456)
        self.assertEqual(lfn[13], installer.lfn_checksum(short_name))

    def test_lfn_rejects_more_than_one_directory_entry(self) -> None:
        short_name = installer.deployment.encode_short_name("LONG~1.BIN")
        with self.assertRaisesRegex(ValueError, "at most 12"):
            installer.one_lfn_entry("THIRTEENCHARS", short_name)

    def test_main_allows_offline_controller(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data.bin"
            nand = root / "nand.raw"
            helper = root / "ecc.exe"
            report = root / "report.json"
            source.write_bytes(b"data")
            nand.write_bytes(b"nand")
            helper.write_bytes(b"helper")
            argv = [
                "install_emulator_path.py", str(source),
                "--nand", str(nand), "--ecc-helper", str(helper),
                "--report", str(report),
            ]
            installed = {"readback_match": True}
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                installer.deployment,
                "api_request",
                side_effect=RuntimeError("offline"),
            ), mock.patch.object(
                installer,
                "install_transactionally",
                return_value=installed,
            ):
                self.assertEqual(installer.main(), 0)
            self.assertFalse(installed["emulator_was_running"])
            self.assertFalse(installed["controller_reachable"])
            self.assertTrue(report.is_file())


if __name__ == "__main__":
    unittest.main()
