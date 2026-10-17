#!/usr/bin/env python3
"""Inspect and repack a JBL Wave Buds 2 OTA package.

Operates on your own copy of an official package.

  inspect    parse the package and confirm an unchanged repack is byte-identical
  make-test  derive a one-byte test image (bumps the "RTX V5.5.1" marker)
  repack     apply arbitrary decompressed-byte patches and rebuild the container

Every path recomputes the inter-stream length fields and the CRC-32 trailer, and
refuses to emit unless an unchanged repack of the source is byte-identical — so a
format-handling error cannot silently produce a corrupt image.

Flashing a modified image is irreversible and there is no recovery path. A
CRC-valid but functionally broken image will still activate. Read docs/04 and
docs/08 first. You do this at your own risk, on a device you own.
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
RTX_MARKER = b"RTX V5.5.1"
LZMA_FILTERS = [{"id": lzma.FILTER_LZMA1, "dict_size": 0x04000000, "lc": 3, "lp": 0, "pb": 2}]


def parse_blocks(packed: bytes) -> tuple[bytes, list[bytes]]:
    trailer = packed.find(CRC_PREFIX)
    if trailer < 8:
        raise ValueError("CRC trailer marker not found")
    if not re.fullmatch(rb"CRC32_OF_IMAGE=0x([0-9A-Fa-f]{8})\n", packed[trailer:]):
        raise ValueError("unexpected CRC trailer shape")
    stored = int(packed[trailer + len(CRC_PREFIX): trailer + len(CRC_PREFIX) + 8], 16)
    if (zlib.crc32(packed[: trailer + len(CRC_PREFIX)]) & 0xFFFFFFFF) != stored:
        raise ValueError("source container CRC does not validate")

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
    for index, (start, end) in enumerate(zip(starts, ends)):
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        chunk = packed[start:end]
        blocks.append(
            decoder.decompress(chunk, max_length=BLOCK_SIZE)
            if index < len(starts) - 1
            else decoder.decompress(chunk)
        )
    if len(blocks) != 8:
        raise ValueError(f"expected 8 LZMA streams; found {len(blocks)}")
    return packed[:8], blocks


def pack(header: bytes, blocks: list[bytes]) -> bytes:
    if len(blocks) != 8 or any(len(b) != BLOCK_SIZE for b in blocks[:-1]):
        raise ValueError("expected 8 blocks, the first seven of 128 KiB")
    streams = [lzma.compress(b, format=lzma.FORMAT_ALONE, filters=LZMA_FILTERS) for b in blocks]
    for index, (block, stream) in enumerate(zip(blocks, streams)):
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        if decoder.decompress(stream) != block or not decoder.eof:
            raise ValueError(f"recompressed stream {index} did not round-trip")

    header = header[:4] + len(streams[0]).to_bytes(4, "big")
    parts = [header]
    for index, stream in enumerate(streams):
        parts.append(stream)
        if index < len(streams) - 1:
            parts.append(len(streams[index + 1]).to_bytes(4, "big"))
    parts.append(CRC_PREFIX)
    body = b"".join(parts)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + f"{crc:08X}\n".encode("ascii")


def _split_blocks(image: bytes) -> list[bytes]:
    return [image[i:i + BLOCK_SIZE] for i in range(0, len(image), BLOCK_SIZE)]


def _require_identity(header: bytes, blocks: list[bytes], packed: bytes) -> None:
    if pack(header, blocks) != packed:
        raise SystemExit("refusing: an unchanged repack of the source is not byte-identical")


def cmd_inspect(args: argparse.Namespace) -> None:
    packed = args.package.read_bytes()
    header, blocks = parse_blocks(packed)
    image = b"".join(blocks)
    print(f"packaged size:      {len(packed)} bytes")
    print(f"package MD5:        {hashlib.md5(packed).hexdigest()}")
    print(f"decompressed total: {len(image)} bytes")
    print(f"block sizes:        {[len(b) for b in blocks]}")
    print(f"unchanged repack byte-identical: {pack(header, blocks) == packed}")
    position = image.find(RTX_MARKER)
    print(f"RTX marker offset:  {position if position >= 0 else 'not found'}")


def cmd_make_test(args: argparse.Namespace) -> None:
    packed = args.source.read_bytes()
    header, blocks = parse_blocks(packed)
    _require_identity(header, blocks, packed)

    image = bytearray(b"".join(blocks))
    index = image.find(RTX_MARKER)
    if index < 0:
        raise SystemExit("RTX marker not found; use `repack --set-byte` for a manual patch")
    position = index + len(RTX_MARKER) - 1  # final digit of "…5.5.1"
    original = image[position]
    image[position] = ord("2") if chr(original) == "1" else (original + 1) & 0xFF

    output = pack(header, _split_blocks(bytes(image)))
    _, verify_blocks = parse_blocks(output)
    verify_image = b"".join(verify_blocks)
    diffs = [i for i, (a, b) in enumerate(zip(b"".join(blocks), verify_image)) if a != b]
    if len(verify_image) != len(image) or diffs != [position]:
        raise SystemExit(f"expected exactly one changed byte at {position}; got {diffs}")

    args.out.write_bytes(output)
    print(f"source:       {args.source}")
    print(f"output:       {args.out} ({len(output)} bytes)")
    print(f"changed byte: decompressed offset {position} "
          f"('{chr(original)}' -> '{chr(image[position])}') in '{RTX_MARKER.decode()}'")
    print(f"package MD5:  {hashlib.md5(output).hexdigest()}")


def _parse_patch(spec: str) -> tuple[int, int]:
    key, value = spec.split("=", 1)
    offset, byte = int(key, 0), int(value, 0)
    if not 0 <= byte <= 255:
        raise ValueError(f"patch value out of byte range: {value}")
    return offset, byte


def cmd_repack(args: argparse.Namespace) -> None:
    packed = args.package.read_bytes()
    header, blocks = parse_blocks(packed)
    _require_identity(header, blocks, packed)

    image = bytearray(b"".join(blocks))
    patches = [_parse_patch(spec) for spec in args.set_byte]
    for offset, byte in patches:
        if not 0 <= offset < len(image):
            raise SystemExit(f"offset {offset} out of range (image is {len(image)} bytes)")
        image[offset] = byte

    output = pack(header, _split_blocks(bytes(image)))
    _, verify_blocks = parse_blocks(output)
    diffs = sum(a != b for a, b in zip(b"".join(blocks), b"".join(verify_blocks)))
    args.out.write_bytes(output)
    print(f"patches:     {[(hex(o), v) for o, v in patches]}")
    print(f"changed bytes: {diffs}")
    print(f"output:      {args.out} ({len(output)} bytes)")
    print(f"package MD5: {hashlib.md5(output).hexdigest()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("package", type=Path)
    p_inspect.set_defaults(func=cmd_inspect)

    p_make = sub.add_parser("make-test")
    p_make.add_argument("source", type=Path)
    p_make.add_argument("out", type=Path)
    p_make.set_defaults(func=cmd_make_test)

    p_repack = sub.add_parser("repack")
    p_repack.add_argument("package", type=Path)
    p_repack.add_argument("out", type=Path)
    p_repack.add_argument("--set-byte", action="append", default=[], metavar="OFFSET=VALUE",
                          help="patch a decompressed byte (hex or decimal); repeatable")
    p_repack.set_defaults(func=cmd_repack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
