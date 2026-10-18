#!/usr/bin/env python3
"""Strict, size-bounded parser for the 8-stream Wave Buds 2 OTA container.

Length fields, not LZMA marker searches, define compressed-stream boundaries.
Validation remains active in optimized Python (-O). No firmware is embedded.
"""
from __future__ import annotations

import lzma
import re
import zlib

BLOCK_SIZE = 0x20000
STREAM_COUNT = 8
MAGIC = b"\xff" * 4
LZMA_HEADER = b"\x5d\x00\x00\x00\x04" + b"\xff" * 8
CRC_PREFIX = b"CRC32_OF_IMAGE=0x"
CRC_TRAILER_SIZE = len(CRC_PREFIX) + 9


def parse(packed: bytes) -> dict:
    if len(packed) < 8 + CRC_TRAILER_SIZE or packed[:4] != MAGIC:
        raise ValueError("invalid OTA package header")
    trailer = len(packed) - CRC_TRAILER_SIZE
    match = re.fullmatch(re.escape(CRC_PREFIX) + rb"([0-9A-Fa-f]{8})\n", packed[trailer:])
    if match is None:
        raise ValueError("invalid OTA CRC trailer at end of package")

    stored_crc = int(match.group(1), 16)
    crc_input_end = trailer + len(CRC_PREFIX)
    calculated_crc = zlib.crc32(packed[:crc_input_end]) & 0xFFFFFFFF
    if stored_crc != calculated_crc:
        raise ValueError("source container CRC-32 mismatch")

    cursor = 8
    first_length = int.from_bytes(packed[4:8], "big")
    starts: list[int] = []
    compressed: list[bytes] = []
    blocks: list[bytes] = []

    for index in range(STREAM_COUNT):
        if index == 0:
            length = first_length
        else:
            if cursor + 4 > trailer:
                raise ValueError(f"missing length field for stream {index}")
            length = int.from_bytes(packed[cursor:cursor + 4], "big")
            cursor += 4

        if length < len(LZMA_HEADER) or cursor + length > trailer:
            raise ValueError(f"invalid compressed length for stream {index}: {length}")
        start = cursor
        stream = packed[start:start + length]
        cursor += length
        if not stream.startswith(LZMA_HEADER):
            raise ValueError(f"unexpected LZMA header in stream {index}")

        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        try:
            block = decoder.decompress(stream, max_length=BLOCK_SIZE + 1)
        except lzma.LZMAError as error:
            raise ValueError(f"cannot decompress stream {index}") from error
        if not decoder.eof or decoder.unused_data:
            raise ValueError(f"stream {index} has an incomplete or trailing LZMA payload")
        if index < STREAM_COUNT - 1:
            if len(block) != BLOCK_SIZE:
                raise ValueError(f"stream {index} must decompress to 128 KiB")
        elif not 0 < len(block) <= BLOCK_SIZE:
            raise ValueError("last stream exceeds 128 KiB or is empty")

        starts.append(start)
        compressed.append(stream)
        blocks.append(block)

    if cursor != trailer:
        raise ValueError(f"{trailer - cursor} unexpected bytes before CRC trailer")

    return {
        "header": packed[:8],
        "header_len0": first_length,
        "streams": STREAM_COUNT,
        "starts": starts,
        "compressed": compressed,
        "blocks": blocks,
        "trailer": trailer,
        "crc_input_end": crc_input_end,
        "stored_crc": stored_crc,
        "calc_crc": calculated_crc,
    }
