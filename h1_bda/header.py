from __future__ import annotations

import struct
from dataclasses import dataclass


HEADER_SIZE = 0x88
HEADER_XOR_KEY = 0x44525744
CHECKSUM_XOR_KEY = 0x322D464B
CHECKSUM_OFFSET = 0x84
ENCODED_WORD_COUNT = 11
MAGIC = 0x004B4242
MARKER = 0x5D245562
VERSION = 0x01000102
CATEGORY_MATH = 0x1E
CATEGORY_OTHER = 0x47
CATEGORY_GAME = 0x48
TITLE_OFFSET = 0x2C
TITLE_SIZE = 16
BUILD_TIME_OFFSET = 0x3C
BUILD_TIME_SIZE = 20
DESCRIPTION_OFFSET = 0x50
DESCRIPTION_SIZE = 20


@dataclass(frozen=True)
class HeaderFields:
    category: int
    file_size_minus_4: int
    payload_offset: int
    resource_offset: int
    resource_sizes: tuple[int, int, int, int]
    version: int = VERSION

    def words(self) -> tuple[int, ...]:
        return (
            MAGIC,
            MARKER,
            self.version,
            self.category,
            self.file_size_minus_4,
            self.payload_offset,
            self.resource_offset,
            *self.resource_sizes,
        )


def _put_text(header: bytearray, offset: int, size: int, text: str) -> None:
    encoded = text.encode("gbk")
    if len(encoded) >= size:
        raise ValueError(f"text at 0x{offset:x} must be shorter than {size} GBK bytes")
    header[offset : offset + size] = encoded + bytes(size - len(encoded))


def encode_header(
    fields: HeaderFields,
    *,
    title: str,
    build_time: str = "",
    description: str = "H1 Native BDA SDK",
) -> bytes:
    header = bytearray(HEADER_SIZE)
    struct.pack_into("<11I", header, 0, *fields.words())
    _put_text(header, TITLE_OFFSET, TITLE_SIZE, title)
    _put_text(header, BUILD_TIME_OFFSET, BUILD_TIME_SIZE, build_time)
    _put_text(header, DESCRIPTION_OFFSET, DESCRIPTION_SIZE, description)

    checksum = sum(header[:CHECKSUM_OFFSET]) & 0xFFFFFFFF
    struct.pack_into("<I", header, CHECKSUM_OFFSET, checksum ^ CHECKSUM_XOR_KEY)
    for index in range(ENCODED_WORD_COUNT):
        offset = index * 4
        value = struct.unpack_from("<I", header, offset)[0]
        struct.pack_into("<I", header, offset, value ^ HEADER_XOR_KEY)
    return bytes(header)


def decode_header(encoded: bytes) -> bytes:
    if len(encoded) < HEADER_SIZE:
        raise ValueError(f"BDA header is shorter than 0x{HEADER_SIZE:x} bytes")
    header = bytearray(encoded[:HEADER_SIZE])
    for index in range(ENCODED_WORD_COUNT):
        offset = index * 4
        value = struct.unpack_from("<I", header, offset)[0]
        struct.pack_into("<I", header, offset, value ^ HEADER_XOR_KEY)
    checksum = struct.unpack_from("<I", header, CHECKSUM_OFFSET)[0]
    struct.pack_into("<I", header, CHECKSUM_OFFSET, checksum ^ CHECKSUM_XOR_KEY)
    return bytes(header)


def read_c_string(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("gbk", errors="replace")
