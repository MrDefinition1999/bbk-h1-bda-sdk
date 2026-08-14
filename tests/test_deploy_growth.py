from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SDK_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SDK_ROOT / "scripts" / "deploy_emulator_bda.py"
SPEC = importlib.util.spec_from_file_location("h1_deploy_growth_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
deployment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = deployment
SPEC.loader.exec_module(deployment)


class FakeVolume:
    def __init__(
        self,
        copies: list[dict[int, int]],
        max_cluster: int = 12,
    ):
        self.geometry = deployment.FatGeometry(
            boot_offset=0,
            bytes_per_sector=512,
            sectors_per_cluster=32,
            reserved_sectors=1,
            fat_copies=len(copies),
            root_entries=512,
            sectors_per_fat=1,
            total_sectors=(max_cluster - 1) * 32 + 35,
        )
        self.copies = copies

    def fat_entry(self, cluster: int, copy_index: int = 0) -> int:
        return self.copies[copy_index].get(cluster, 0)

class DeployGrowthTests(unittest.TestCase):
    def test_main_allows_offline_controller(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            replacement = root / "test.bda"
            nand = root / "nand.raw"
            helper = root / "ecc.exe"
            report = root / "report.json"
            replacement.write_bytes(b"bda")
            nand.write_bytes(b"nand")
            helper.write_bytes(b"helper")
            argv = [
                "deploy_emulator_bda.py", "--bda", str(replacement),
                "--nand", str(nand), "--ecc-helper", str(helper),
                "--report", str(report),
            ]
            deployed = {"readback_match": True}
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                deployment,
                "api_request",
                side_effect=RuntimeError("offline"),
            ), mock.patch.object(
                deployment,
                "deploy_transactionally",
                return_value=deployed,
            ):
                self.assertEqual(deployment.main(), 0)
            self.assertFalse(deployed["emulator_was_running"])
            self.assertFalse(deployed["controller_reachable"])
            self.assertTrue(report.is_file())

    def test_conservative_fat_short_name(self) -> None:
        self.assertEqual(deployment.encode_short_name("SAMPLE.DAT"), b"SAMPLE  DAT")
        with self.assertRaises(ValueError):
            deployment.encode_short_name("TOO-LONG-NAME.DAT")

    def test_required_cluster_count_rounds_up(self) -> None:
        self.assertEqual(deployment.required_cluster_count(0, 16384), 0)
        self.assertEqual(deployment.required_cluster_count(1, 16384), 1)
        self.assertEqual(deployment.required_cluster_count(16384, 16384), 1)
        self.assertEqual(deployment.required_cluster_count(16385, 16384), 2)

    def test_select_free_clusters_requires_all_fat_copies_to_agree(self) -> None:
        volume = FakeVolume(
            [
                {2: 0xFFFF, 3: 0, 4: 0, 5: 0},
                {2: 0xFFFF, 3: 0xFFFF, 4: 0, 5: 0},
            ],
        )
        self.assertEqual(deployment.select_free_clusters(volume, 2), [4, 5])

    def test_select_free_clusters_fails_when_space_is_insufficient(self) -> None:
        used = {cluster: 0xFFFF for cluster in range(2, 13)}
        volume = FakeVolume([used, used])
        with self.assertRaisesRegex(ValueError, "mutually free clusters"):
            deployment.select_free_clusters(volume, 1)

    def test_allocate_ftl_records_reuses_mapping_and_allocates_after_bbt(self) -> None:
        record = deployment.h1_ftl.FtlRecord
        mapped = record(80, 0, "mapped", sequence=7, logical=5)
        scan = type(
            "Scan",
            (),
            {
                "mapping": {5: mapped},
                "records": (
                    record(90, 0, "free"),
                    record(100, 0, "bbt", logical=None),
                    record(101, 0, "free"),
                ),
            },
        )()
        selected, allocated = deployment.allocate_ftl_records(scan, {5, 6})
        self.assertIs(selected[5], mapped)
        self.assertEqual(selected[6].physical_block, 101)
        self.assertEqual(set(allocated), {6})


if __name__ == "__main__":
    unittest.main()
