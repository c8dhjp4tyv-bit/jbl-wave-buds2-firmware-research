#!/usr/bin/env python3
"""Inventory a JBL Wave Buds 2 OTA package into machine-readable metadata.

Operates on YOUR OWN copy of an official package. Emits a per-stream layout CSV
and a package-inventory JSON. Contains no firmware bytes — only offsets, sizes,
hashes, and the CRC value. Format reference: docs/02-ota-container-format.md.

    python3 inventory_ota_container.py <package.bin> --csv layout.csv --json inv.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import zlib
from pathlib import Path

BLOCK_SIZE = 0x20000
LZMA_HEADER = b"\x5d\x00\x00\x00\x04" + b"\xff" * 8
CRC_PREFIX = b"CRC32_OF_IMAGE=0x"


def inventory(packed: bytes) -> dict:
    trailer = packed.find(CRC_PREFIX)
    match = re.fullmatch(rb"CRC32_OF_IMAGE=0x([0-9A-Fa-f]{8})\n", packed[trailer:])
    if trailer < 8 or not match:
        raise ValueError("not a recognized OTA package (missing/!malformed CRC trailer)")
    stored_crc = int(match.group(1), 16)
    crc_input_end = trailer + len(CRC_PREFIX)
    calc_crc = zlib.crc32(packed[:crc_input_end]) & 0xFFFFFFFF

    starts, cursor = [], 8
    while True:
        cursor = packed.find(LZMA_HEADER, cursor, trailer)
        if cursor < 0:
            break
        starts.append(cursor)
        cursor += len(LZMA_HEADER)
    ends = starts[1:] + [trailer]

    streams, image_offset = [], 0
    image_hash = hashlib.sha256()
    for index, (start, end) in enumerate(zip(starts, ends)):
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        chunk = packed[start:end]
        block = decoder.decompress(chunk, max_length=BLOCK_SIZE) if index < len(starts) - 1 else decoder.decompress(chunk)
        comp = chunk[:-4] if index < len(starts) - 1 else chunk
        image_hash.update(block)
        streams.append({
            "index": index,
            "file_offset": start,
            "compressed_size": len(comp),
            "decompressed_size": len(block),
            "image_offset": image_offset,
        })
        image_offset += len(block)

    return {
        "packaged_size": len(packed),
        "package_md5": hashlib.md5(packed).hexdigest(),
        "package_sha256": hashlib.sha256(packed).hexdigest(),
        "header_hex": packed[:8].hex(),
        "stream_count": len(streams),
        "decompressed_size": image_offset,
        "image_sha256": image_hash.hexdigest(),
        "trailer_offset": trailer,
        "crc_input_end": crc_input_end,
        "crc_stored": f"{stored_crc:08X}",
        "crc_computed": f"{calc_crc:08X}",
        "crc_valid": stored_crc == calc_crc,
        "streams": streams,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    info = inventory(args.package.read_bytes())

    if args.csv:
        import csv
        with args.csv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["index", "file_offset", "compressed_size", "decompressed_size", "image_offset"])
            writer.writeheader()
            writer.writerows(info["streams"])
        print(f"{info['stream_count']} streams -> {args.csv}")
    if args.json:
        summary = {k: v for k, v in info.items() if k != "streams"}
        args.json.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"package inventory -> {args.json}")
    if not args.csv and not args.json:
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
