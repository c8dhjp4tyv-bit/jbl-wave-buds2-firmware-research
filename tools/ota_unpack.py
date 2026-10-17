#!/usr/bin/env python3
"""Parse a JBL Wave Buds 2 OTA package and report its structure.

Operates on your own copy of an official package; it does not modify anything.
Format reference: docs/02-ota-container-format.md.

    python3 ota_unpack.py <official_package.bin> [--extract image.bin]
"""
from __future__ import annotations

import argparse
import hashlib
import lzma
import re
import zlib
from pathlib import Path

BLOCK_SIZE = 0x20000
LZMA_HEADER = b"\x5d\x00\x00\x00\x04" + b"\xff" * 8
CRC_PREFIX = b"CRC32_OF_IMAGE=0x"


def parse(packed: bytes) -> dict:
    trailer = packed.find(CRC_PREFIX)
    if trailer < 8:
        raise ValueError("CRC trailer marker not found")
    match = re.fullmatch(rb"CRC32_OF_IMAGE=0x([0-9A-Fa-f]{8})\n", packed[trailer:])
    if not match:
        raise ValueError("unexpected CRC trailer shape")

    stored_crc = int(match.group(1), 16)
    crc_input_end = trailer + len(CRC_PREFIX)
    calc_crc = zlib.crc32(packed[:crc_input_end]) & 0xFFFFFFFF
    header_len0 = int.from_bytes(packed[4:8], "big")

    starts: list[int] = []
    cursor = 8
    while True:
        cursor = packed.find(LZMA_HEADER, cursor, trailer)
        if cursor < 0:
            break
        starts.append(cursor)
        cursor += len(LZMA_HEADER)
    if not starts or starts[0] != 8:
        raise ValueError("first LZMA stream is not at offset 8")
    ends = starts[1:] + [trailer]

    blocks: list[bytes] = []
    compressed: list[bytes] = []
    for index, (start, end) in enumerate(zip(starts, ends)):
        chunk = packed[start:end]
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        if index < len(starts) - 1:
            blocks.append(decoder.decompress(chunk, max_length=BLOCK_SIZE))
            compressed.append(chunk[:-4])  # drop the trailing next-stream length field
        else:
            blocks.append(decoder.decompress(chunk))
            compressed.append(chunk)

    return {
        "header": packed[:8],
        "header_len0": header_len0,
        "streams": len(starts),
        "compressed": compressed,
        "blocks": blocks,
        "trailer": trailer,
        "crc_input_end": crc_input_end,
        "stored_crc": stored_crc,
        "calc_crc": calc_crc,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", type=Path)
    parser.add_argument("--extract", type=Path, help="write the decompressed image to this path")
    args = parser.parse_args()

    packed = args.package.read_bytes()
    info = parse(packed)
    image = b"".join(info["blocks"])

    print(f"file:                {args.package}")
    print(f"packaged size:       {len(packed)} bytes")
    print(f"package MD5:         {hashlib.md5(packed).hexdigest()}")
    print(f"header:              {info['header'].hex()}")
    print(f"stream count:        {info['streams']}")
    print(f"compressed sizes:    {[len(c) for c in info['compressed']]}")
    print(f"header stream-0 len: {info['header_len0']} "
          f"(matches: {info['header_len0'] == len(info['compressed'][0])})")
    print(f"decompressed sizes:  {[len(b) for b in info['blocks']]}")
    print(f"decompressed total:  {len(image)} bytes")
    print(f"trailer offset:      0x{info['trailer']:X}")
    print(f"CRC input range:     [0, 0x{info['crc_input_end']:X})")
    print(f"stored CRC-32:       {info['stored_crc']:08X}")
    valid = info["stored_crc"] == info["calc_crc"]
    print(f"computed CRC-32:     {info['calc_crc']:08X}  ({'valid' if valid else 'MISMATCH'})")

    if args.extract:
        args.extract.write_bytes(image)
        print(f"decompressed image:  -> {args.extract} ({len(image)} bytes)")


if __name__ == "__main__":
    main()
