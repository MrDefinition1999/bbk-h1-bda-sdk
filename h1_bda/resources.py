from __future__ import annotations

import struct
from pathlib import Path
from collections.abc import Sequence


RESOURCE_OFFSET = 0x88
PAYLOAD_OFFSET = 0x785C
RESOURCE_SIZES = (0x17C8, 0x2620, 0x1704, 0x22E8)
RESOURCE_SPECS = (
    (45, 45, 24),
    (57, 57, 24),
    (49, 60, 16),
    (49, 60, 16),
)


def rgb565(red: int, green: int, blue: int) -> int:
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def _diagnostic_pixel(
    x: int, y: int, width: int, height: int
) -> tuple[int, int, int, int]:
    border = x < 3 or y < 3 or x >= width - 3 or y >= height - 3
    cross = abs(x - y) <= 1 or abs((width - 1 - x) - y) <= 1
    if border:
        return 250, 250, 250, 255
    if cross:
        return 20, 185, 110, 255
    return 20, 45, 70, 235


def _make_resource(width: int, height: int, bits: int, size: int) -> bytes:
    pixels = [
        _diagnostic_pixel(x, y, width, height)
        for y in range(height)
        for x in range(width)
    ]
    return _pack_resource(width, height, bits, size, pixels)


def _pack_resource(
    width: int,
    height: int,
    bits: int,
    size: int,
    pixels: Sequence[tuple[int, int, int, int]],
) -> bytes:
    if len(pixels) != width * height:
        raise ValueError(
            f"H1 icon has {len(pixels)} pixels, expected {width * height}"
        )
    result = bytearray(struct.pack("<6H", width, height, bits, 1, width, height))
    for red, green, blue, alpha in pixels:
        if bits == 24:
            # H1's 24-bit menu bitmap is RGB565 little-endian plus alpha.
            result.extend(struct.pack("<HB", rgb565(red, green, blue), alpha))
        elif bits == 16:
            # These resources have no alpha channel. Composite transparent
            # source pixels against the menu's black image background.
            if alpha < 255:
                red = red * alpha // 255
                green = green * alpha // 255
                blue = blue * alpha // 255
            result.extend(struct.pack("<H", rgb565(red, green, blue)))
        else:
            raise ValueError(f"unsupported H1 icon depth: {bits}")
    if len(result) > size:
        raise ValueError(
            f"H1 resource {width}x{height}x{bits} exceeds 0x{size:x} bytes"
        )
    result.extend(bytes(size - len(result)))
    return bytes(result)


def build_diagnostic_resources() -> bytes:
    resources = b"".join(
        _make_resource(width, height, bits, size)
        for (width, height, bits), size in zip(RESOURCE_SPECS, RESOURCE_SIZES)
    )
    expected = PAYLOAD_OFFSET - RESOURCE_OFFSET
    if len(resources) != expected:
        raise AssertionError(
            f"H1 resource region is 0x{len(resources):x}, expected 0x{expected:x}"
        )
    return resources


def build_icon_resources(icon_png: Path) -> bytes:
    """Convert one RGBA PNG into the four fixed H1 menu icon resources."""
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "custom H1 icons require Pillow; install the h1-bda-sdk package"
        ) from error

    with Image.open(icon_png) as opened:
        source = opened.convert("RGBA")
    if source.width <= 0 or source.height <= 0:
        raise ValueError("H1 icon PNG must have non-zero dimensions")

    resources = bytearray()
    resampling = Image.Resampling.LANCZOS
    for (width, height, bits), size in zip(RESOURCE_SPECS, RESOURCE_SIZES):
        scale = min(width / source.width, height / source.height)
        draw_width = max(1, min(width, round(source.width * scale)))
        draw_height = max(1, min(height, round(source.height * scale)))
        resized = source.resize((draw_width, draw_height), resampling)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        image.alpha_composite(
            resized,
            ((width - draw_width) // 2, (height - draw_height) // 2),
        )
        get_pixels = getattr(image, "get_flattened_data", image.getdata)
        resources.extend(
            _pack_resource(
                width,
                height,
                bits,
                size,
                list(get_pixels()),
            )
        )

    expected = PAYLOAD_OFFSET - RESOURCE_OFFSET
    if len(resources) != expected:
        raise AssertionError(
            f"H1 resource region is 0x{len(resources):x}, expected 0x{expected:x}"
        )
    return bytes(resources)
