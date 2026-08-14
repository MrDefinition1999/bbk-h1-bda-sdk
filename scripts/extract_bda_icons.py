#!/usr/bin/env python3
"""Extract the four menu icon resources from a normal BBK H1 BDA."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image


SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from h1_bda.header import decode_header, read_c_string


def expand_rgb565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    return (
        (red << 3) | (red >> 2),
        (green << 2) | (green >> 4),
        (blue << 3) | (blue >> 2),
    )


def extract_icons(source: Path, output_dir: Path) -> list[Path]:
    data = source.read_bytes()
    decoded = decode_header(data)
    words = struct.unpack_from("<11I", decoded, 0)
    offset = words[6]
    output_dir.mkdir(parents=True, exist_ok=True)
    title = read_c_string(decoded[0x2C:0x3C]) or source.stem
    outputs: list[Path] = []
    for index, size in enumerate(words[7:11]):
        if size < 12 or offset + size > len(data):
            raise ValueError(f"resource {index} is outside {source}")
        width, height, bits, planes, draw_width, draw_height = struct.unpack_from(
            "<6H", data, offset
        )
        if planes != 1 or (draw_width, draw_height) != (width, height):
            raise ValueError(f"resource {index} has an unsupported image header")
        pixel_size = bits // 8
        pixel_end = offset + 12 + width * height * pixel_size
        if bits not in (16, 24) or pixel_end > offset + size:
            raise ValueError(f"resource {index} has an unsupported pixel layout")
        pixels: list[tuple[int, int, int, int]] = []
        cursor = offset + 12
        for _ in range(width * height):
            color = struct.unpack_from("<H", data, cursor)[0]
            red, green, blue = expand_rgb565(color)
            alpha = data[cursor + 2] if bits == 24 else 255
            pixels.append((red, green, blue, alpha))
            cursor += pixel_size
        image = Image.new("RGBA", (width, height))
        image.putdata(pixels)
        destination = output_dir / f"{title}-{index}-{width}x{height}x{bits}.png"
        image.save(destination)
        outputs.append(destination)
        offset += size
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bda", type=Path)
    parser.add_argument("-o", "--output-dir", required=True, type=Path)
    args = parser.parse_args()
    for output in extract_icons(args.bda, args.output_dir):
        print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
