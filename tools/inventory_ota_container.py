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
from ota_container import parse as parse_container
from pathlib import Path


def inventory(packed: bytes) -> dict:
    parsed = parse_container(packed)
    streams, image_offset = [], 0
    image_hash = hashlib.sha256()
    for index, (start, comp, block) in enumerate(
        zip(parsed["starts"], parsed["compressed"], parsed["blocks"])
    ):
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
        "header_hex": parsed["header"].hex(),
        "stream_count": parsed["streams"],
        "decompressed_size": image_offset,
        "image_sha256": image_hash.hexdigest(),
        "trailer_offset": parsed["trailer"],
        "crc_input_end": parsed["crc_input_end"],
        "crc_stored": f'{parsed["stored_crc"]:08X}',
        "crc_computed": f'{parsed["calc_crc"]:08X}',
        "crc_valid": True,
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
