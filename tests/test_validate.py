from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from h1_bda.header import HeaderFields, encode_header
from h1_bda.resources import (
    PAYLOAD_OFFSET,
    RESOURCE_OFFSET,
    RESOURCE_SIZES,
    build_diagnostic_resources,
)
from h1_bda.validate import validate_bda


def make_bda() -> bytes:
    payload = struct.pack("<II", 0x03E00008, 0)
    size = PAYLOAD_OFFSET + len(payload)
    header = encode_header(
        HeaderFields(
            category=0x48,
            file_size_minus_4=size - 4,
            payload_offset=PAYLOAD_OFFSET,
            resource_offset=RESOURCE_OFFSET,
            resource_sizes=RESOURCE_SIZES,
        ),
        title="Validator",
    )
    return header + build_diagnostic_resources() + payload


class ValidateTests(unittest.TestCase):
    def validate(self, data: bytes) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.bda"
            path.write_bytes(data)
            return validate_bda(path)

    def test_accepts_valid_h1_bda(self) -> None:
        report = self.validate(make_bda())
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["payload_offset"], PAYLOAD_OFFSET)
        self.assertEqual(len(report["resources"]), 4)

    def test_rejects_wrong_length_field(self) -> None:
        data = bytearray(make_bda())
        data.extend(b"\x00\x00\x00\x00")
        report = self.validate(data)
        self.assertFalse(report["ok"])
        self.assertTrue(any("file_size_minus_4" in error for error in report["errors"]))

    def test_rejects_corrupted_header_checksum(self) -> None:
        data = bytearray(make_bda())
        data[0x2C] ^= 1
        report = self.validate(data)
        self.assertFalse(report["checksum_ok"])

    def test_rejects_resource_overflow(self) -> None:
        data = bytearray(make_bda())
        # Resource sizes are in encoded word 7..10; enlarging word 10 also
        # invalidates the checksum, but the resource-boundary error must remain.
        encoded = struct.unpack_from("<I", data, 40)[0]
        struct.pack_into("<I", data, 40, encoded ^ 0x1000)
        report = self.validate(data)
        self.assertFalse(report["ok"])
        self.assertTrue(any("resource" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
