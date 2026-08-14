from __future__ import annotations

import unittest
import struct
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from h1_bda.build import (
    _build_timestamp,
    _find_binary_tool,
    build_bda,
    compile_sources,
)
from h1_bda.header import decode_header


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class MultiSourceBuildTests(unittest.TestCase):
    def test_source_date_epoch_makes_header_timestamp_reproducible(self) -> None:
        with patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "1785456000"}):
            self.assertEqual(_build_timestamp(), "2026-07-31 00:00:00")

    def test_invalid_source_date_epoch_is_rejected(self) -> None:
        with patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "invalid"}):
            with self.assertRaisesRegex(ValueError, "valid Unix timestamp"):
                _build_timestamp()

    def test_links_symbols_across_sources(self) -> None:
        sources = [FIXTURES / "multi_entry.c", FIXTURES / "multi_helper.c"]
        payload = compile_sources(sources, [])
        self.assertGreater(len(payload), 0)

    def test_multi_source_bda_passes_header_validation(self) -> None:
        sources = [FIXTURES / "multi_entry.c", FIXTURES / "multi_helper.c"]
        data = build_bda(sources, "MultiSource", 0x1E, [])
        header = decode_header(data)
        self.assertEqual(struct.unpack_from("<I", header, 0x10)[0], len(data) - 4)

    def test_noinit_reserves_ram_without_expanding_payload(self) -> None:
        payload = compile_sources([FIXTURES / "noinit_entry.c"], [])
        self.assertLess(len(payload), 4096)

    def test_source_paths_are_mapped_out_of_release_payload(self) -> None:
        payload = compile_sources([FIXTURES / "path_entry.c"], [])
        self.assertNotIn(str(Path.home()).encode(), payload)
        self.assertNotIn(str(FIXTURES.parents[1]).encode(), payload)
        self.assertIn(b"h1-sdk", payload)

    def test_noinit_can_be_placed_at_a_fixed_runtime_address(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            debug_elf = Path(temporary) / "fixed-noinit.elf"
            payload = compile_sources(
                [FIXTURES / "noinit_entry.c"],
                [],
                debug_elf=debug_elf,
                noinit_address=0x83D00000,
            )
            readelf = subprocess.run(
                [str(_find_binary_tool("llvm-readelf", "readelf")),
                 "-S", str(debug_elf)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        self.assertIn(".h1_noinit", readelf)
        self.assertIn("83d00000", readelf.lower())
        self.assertLess(len(payload), 4096)

    def test_v2_entry_address_is_explicitly_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            debug_elf = Path(temporary) / "v2-entry.elf"
            compile_sources(
                [FIXTURES / "multi_entry.c", FIXTURES / "multi_helper.c"],
                [],
                debug_elf=debug_elf,
                entry_va=0x83C00040,
            )
            header = subprocess.run(
                [
                    str(_find_binary_tool("llvm-readelf", "readelf")),
                    "-h",
                    str(debug_elf),
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        self.assertIn("0x83c00040", header.lower())

    def test_guest_stack_precedes_aligned_game_arena(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            debug_elf = Path(temporary) / "ordered-noinit.elf"
            payload = compile_sources(
                [FIXTURES / "ordered_noinit_entry.c"],
                [],
                debug_elf=debug_elf,
                noinit_address=0x83C80000,
            )
            symbols = subprocess.run(
                [str(_find_binary_tool("llvm-nm", "nm")),
                 "-n", str(debug_elf)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        addresses = {
            line.split()[-1]: int(line.split()[0], 16)
            for line in symbols.splitlines()
            if line.split()[-1] in {"guest_stack", "guest_arena"}
        }
        self.assertEqual(addresses["guest_stack"], 0x83C80000)
        self.assertEqual(addresses["guest_arena"], 0x83D00000)
        self.assertLess(len(payload), 4096)


if __name__ == "__main__":
    unittest.main()
