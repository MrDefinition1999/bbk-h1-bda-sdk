from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from h1_bda.header import (
    CHECKSUM_OFFSET,
    MAGIC,
    MARKER,
    HeaderFields,
    decode_header,
    encode_header,
)
from h1_bda.resources import (
    PAYLOAD_OFFSET,
    RESOURCE_OFFSET,
    RESOURCE_SIZES,
    build_diagnostic_resources,
    build_icon_resources,
    rgb565,
)


class HeaderTests(unittest.TestCase):
    def test_round_trip_and_checksum(self) -> None:
        fields = HeaderFields(
            category=0x47,
            file_size_minus_4=0x8000,
            payload_offset=PAYLOAD_OFFSET,
            resource_offset=RESOURCE_OFFSET,
            resource_sizes=RESOURCE_SIZES,
        )
        decoded = decode_header(encode_header(fields, title="H1 SDK"))
        words = struct.unpack_from("<11I", decoded, 0)
        self.assertEqual(words[0], MAGIC)
        self.assertEqual(words[1], MARKER)
        self.assertEqual(words[5], PAYLOAD_OFFSET)
        self.assertEqual(words[7:11], RESOURCE_SIZES)
        self.assertEqual(
            struct.unpack_from("<I", decoded, CHECKSUM_OFFSET)[0],
            sum(decoded[:CHECKSUM_OFFSET]),
        )

    def test_h1_24_bit_resource_is_rgb565_plus_alpha(self) -> None:
        resources = build_diagnostic_resources()
        self.assertEqual(
            struct.unpack_from("<6H", resources, 0),
            (45, 45, 24, 1, 45, 45),
        )
        self.assertEqual(
            resources[12:15],
            struct.pack("<HB", rgb565(250, 250, 250), 255),
        )

        interior_offset = 12 + (8 * 45 + 4) * 3
        self.assertEqual(
            resources[interior_offset : interior_offset + 3],
            struct.pack("<HB", rgb565(20, 45, 70), 235),
        )

    def test_resource_region_keeps_h1_declared_sizes(self) -> None:
        resources = build_diagnostic_resources()
        self.assertEqual(len(resources), PAYLOAD_OFFSET - RESOURCE_OFFSET)
        self.assertEqual(resources[RESOURCE_SIZES[0] - 1], 0)

    def test_png_icon_is_contained_and_encoded_for_each_h1_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            icon = Path(temporary) / "icon.png"
            image = Image.new("RGBA", (2, 2), (248, 64, 24, 255))
            image.save(icon)
            resources = build_icon_resources(icon)

        self.assertEqual(len(resources), PAYLOAD_OFFSET - RESOURCE_OFFSET)
        offset = 0
        for (width, height, bits), size in zip(
            ((45, 45, 24), (57, 57, 24), (49, 60, 16), (49, 60, 16)),
            RESOURCE_SIZES,
        ):
            self.assertEqual(
                struct.unpack_from("<6H", resources, offset),
                (width, height, bits, 1, width, height),
            )
            center = offset + 12 + ((height // 2) * width + width // 2) * (bits // 8)
            self.assertEqual(
                resources[center : center + 2],
                struct.pack("<H", rgb565(248, 64, 24)),
            )
            if bits == 24:
                self.assertEqual(resources[center + 2], 255)
            offset += size


if __name__ == "__main__":
    unittest.main()
