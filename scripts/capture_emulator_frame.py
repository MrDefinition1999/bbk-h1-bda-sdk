#!/usr/bin/env python3
"""Capture the current H1 emulator framebuffer as a dependency-free PNG."""

from __future__ import annotations

import argparse
import binascii
import struct
import urllib.request
import zlib
from pathlib import Path


FRAME_HEADER = struct.Struct("<4sIIIII")
FRAME_FORMAT_XRGB8888 = 0x34325258
FRAME_FORMAT_RGBA8888 = 0x41424752


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body))


def encode_png(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("RGBA payload size does not match dimensions")
    rows = b"".join(
        b"\0" + rgba[y * width * 4 : (y + 1) * width * 4]
        for y in range(height)
    )
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(rows, 9)),
            png_chunk(b"IEND", b""),
        )
    )


def convert_frame(packet: bytes) -> tuple[int, int, bytes]:
    if len(packet) < FRAME_HEADER.size:
        raise ValueError("frame packet is shorter than its header")
    magic, _sequence, width, height, stride, frame_format = FRAME_HEADER.unpack_from(packet)
    if magic != b"H1FR" or stride != width * 4:
        raise ValueError("unexpected H1 frame header")
    pixels = packet[FRAME_HEADER.size : FRAME_HEADER.size + stride * height]
    if len(pixels) != stride * height:
        raise ValueError("frame packet is truncated")
    if frame_format == FRAME_FORMAT_RGBA8888:
        return width, height, pixels
    if frame_format == FRAME_FORMAT_XRGB8888:
        rgba = bytearray(len(pixels))
        for offset in range(0, len(pixels), 4):
            rgba[offset] = pixels[offset + 2]
            rgba[offset + 1] = pixels[offset + 1]
            rgba[offset + 2] = pixels[offset]
            rgba[offset + 3] = 0xFF
        return width, height, bytes(rgba)
    raise ValueError(f"unsupported H1 frame format 0x{frame_format:08X}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8793")
    args = parser.parse_args()

    with urllib.request.urlopen(args.server.rstrip("/") + "/api/debug/frame", timeout=10) as response:
        packet = response.read()
    width, height, rgba = convert_frame(packet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encode_png(width, height, rgba))
    print(f"output={args.output}")
    print(f"size={width}x{height}")


if __name__ == "__main__":
    main()
