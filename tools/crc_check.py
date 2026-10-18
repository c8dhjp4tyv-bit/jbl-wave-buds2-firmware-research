#!/usr/bin/env python3
"""Verify the CRC-32 trailer of a JBL Wave Buds 2 OTA package.

Recipe (docs/02-ota-container-format.md): standard CRC-32 (identical to
zlib.crc32) computed over the file from offset 0 through the last byte of the
ASCII prefix "CRC32_OF_IMAGE=0x", inclusive — i.e. everything before the hex
digits.

    python3 crc_check.py <official_package.bin>
    python3 crc_check.py --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
import zlib
from pathlib import Path

PREFIX = b"CRC32_OF_IMAGE=0x"


def check(packed: bytes) -> tuple[int, int, int]:
    trailer_length = len(PREFIX) + 9
    if len(packed) < trailer_length:
        raise ValueError("missing CRC trailer")
    index = len(packed) - trailer_length
    match = re.fullmatch(re.escape(PREFIX) + rb"([0-9A-Fa-f]{8})\n", packed[index:])
    if match is None:
        raise ValueError("unexpected CRC trailer shape")
    stored = int(match.group(1), 16)
    cut = index + len(PREFIX)
    calculated = zlib.crc32(packed[:cut]) & 0xFFFFFFFF
    return stored, calculated, cut


def selftest() -> None:
    # Construct a buffer that ends in the trailer, compute the CRC with the
    # documented recipe, and confirm it round-trips. No external file needed.
    body = b"\x00\x01\x02 synthetic payload " + PREFIX
    crc = zlib.crc32(body) & 0xFFFFFFFF
    package = body + f"{crc:08X}\n".encode("ascii")
    stored, calculated, _ = check(package)
    if not (stored == calculated == crc):  # not an assert: must stay active under -O
        raise SystemExit("selftest FAILED")
    print(f"selftest: OK (crc={crc:08X})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", type=Path, nargs="?")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.package:
        parser.error("package path required (or use --selftest)")

    stored, calculated, cut = check(args.package.read_bytes())
    print(f"CRC input range: [0, 0x{cut:X})")
    print(f"stored:          {stored:08X}")
    print(f"computed:        {calculated:08X}")
    valid = stored == calculated
    print("valid" if valid else "MISMATCH")
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
