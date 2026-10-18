#!/usr/bin/env python3
"""Extract the factory/engineering command table from a decompressed image.

Operates on YOUR OWN decompressed application image (produce it with
`ota_unpack.py <package> --extract image.bin`). The table is an array of 8-byte
`[handler_ptr][name_ptr]` entries; both are absolute code/rodata pointers in the
`0x2C010000`-based address space (the image also appears under the `0x0C`
exec-alias, which is normalized here). The table's offset differs between builds,
so this tool locates it structurally — the longest run of consecutive entries
whose pointers resolve inside the image and whose name resolves to a short
uppercase-ASCII token — rather than assuming a fixed address.

    python3 extract_factory_table.py image.bin -o factory_command_table.csv

See docs/10-factory-console.md.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

IMAGE_BASE = 0x2C010000
NAME_RE = re.compile(rb"[A-Z0-9+=,_]{1,20}\x00")


def va_to_off(va: int, base: int) -> int:
    # Both the cached (0x2C) and exec-alias (0x0C) windows map to the same image;
    # the low 24 bits minus the 0x10000 code offset give the file offset.
    return (va & 0x00FFFFFF) - ((base & 0x00FFFFFF))


def read_name(data: bytes, off: int) -> str | None:
    if not (0 <= off < len(data)):
        return None
    match = NAME_RE.match(data, off)
    if not match or match.start() != off:
        return None
    return data[off:match.end() - 1].decode("ascii", "replace")


def valid_entry(data: bytes, pos: int, base: int) -> tuple[int, int, str] | None:
    if pos + 8 > len(data):
        return None
    handler = int.from_bytes(data[pos:pos + 4], "little")
    name_ptr = int.from_bytes(data[pos + 4:pos + 8], "little")
    if (handler >> 24) not in (0x0C, 0x2C) or (name_ptr >> 24) not in (0x0C, 0x2C):
        return None
    handler_off = va_to_off(handler, base)
    if not (0x400 <= handler_off < len(data)):
        return None
    name = read_name(data, va_to_off(name_ptr, base))
    if name is None:
        return None
    handler_va = (handler & 0x00FFFFFF) | (base & 0xFF000000)
    return handler_va, name_ptr, name


def locate_table(data: bytes, base: int, min_run: int) -> int:
    best_start, best_len = -1, 0
    pos = 0
    limit = len(data) - 8
    while pos <= limit:
        if valid_entry(data, pos, base) is None:
            pos += 4
            continue
        run, cur = 0, pos
        while cur <= limit and valid_entry(data, cur, base) is not None:
            run += 1
            cur += 8
        if run > best_len:
            best_len, best_start = run, pos
        pos = cur if run else pos + 4
    if best_len < min_run:
        raise ValueError(f"no command table found (longest run {best_len} < {min_run})")
    return best_start


def extract(data: bytes, base: int, min_run: int) -> list[dict]:
    start = locate_table(data, base, min_run)
    rows, i, pos = [], 0, start
    while True:
        entry = valid_entry(data, pos, base)
        if entry is None:
            break
        handler_va, name_ptr, raw = entry
        rows.append({
            "index": i,
            "command": raw.rstrip(","),
            "takes_arg": int(raw.endswith(",")),
            "handler_va": f"0x{handler_va:08X}",
            "name_va": f"0x{name_ptr:08X}",
        })
        i += 1
        pos += 8
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="decompressed application image")
    parser.add_argument("--base", type=lambda s: int(s, 0), default=IMAGE_BASE)
    parser.add_argument("--min-run", type=int, default=25, help="minimum consecutive entries to accept as the table")
    parser.add_argument("-o", "--out", type=Path, help="CSV output (default: stdout)")
    args = parser.parse_args()

    rows = extract(args.image.read_bytes(), args.base, args.min_run)
    stream = args.out.open("w", newline="") if args.out else sys.stdout
    writer = csv.DictWriter(stream, fieldnames=["index", "command", "takes_arg", "handler_va", "name_va"])
    writer.writeheader()
    writer.writerows(rows)
    if args.out:
        stream.close()
        print(f"{len(rows)} entries -> {args.out}")


if __name__ == "__main__":
    main()
