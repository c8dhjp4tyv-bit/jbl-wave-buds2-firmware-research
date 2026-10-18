#!/usr/bin/env python3
"""Parse a JBL Wave Buds 2 OTA package and report its structure.

Operates on your own copy of an official package; it does not modify anything.
Format reference: docs/02-ota-container-format.md.

    python3 ota_unpack.py <official_package.bin> [--extract image.bin]
"""
from __future__ import annotations

import argparse
import hashlib
from ota_container import parse as parse_container
from pathlib import Path


def parse(packed: bytes) -> dict:
    """Parse a package with the shared strict length-directed parser."""
    return parse_container(packed)


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
