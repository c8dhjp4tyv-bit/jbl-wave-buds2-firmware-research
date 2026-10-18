#!/usr/bin/env python3
"""Export a full function/string/segment inventory from an open IDA database.

Run inside IDA (File > Script file) or headless:

    idat -A -S"tools/export_ida_inventory.py docs/generated" wavebuds.elf.i64

It writes, into the output directory:
  - function_inventory.csv  (every function: va, size, name, is_named)
  - string_inventory.csv    (every string: va, length, text)
  - segments.csv            (segment layout)

This regenerates the full per-function enumeration that is too large and too
noisy (mostly auto-named `sub_*`) to keep inline in the repository. The curated,
reverse-engineered subset is in `analyzed_functions.csv`. The inventory contains
only addresses, sizes, and names derived from your own analysis database — no
firmware bytes.

Requires IDA (idapython). It is a no-op outside IDA.
"""
from __future__ import annotations

import csv
import os
import sys

try:
    import idautils
    import idc
    import ida_funcs
    import ida_segment
    import ida_bytes
    import ida_nalt
except Exception:  # pragma: no cover - only runs inside IDA
    sys.stderr.write("export_ida_inventory.py must run inside IDA (idapython).\n")
    raise SystemExit(1)


def out_dir() -> str:
    args = idc.ARGV[1:] if hasattr(idc, "ARGV") else []
    directory = args[0] if args else "."
    os.makedirs(directory, exist_ok=True)
    return directory


def export_functions(path: str) -> int:
    count = 0
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["va", "size", "name", "is_named"])
        for ea in idautils.Functions():
            func = ida_funcs.get_func(ea)
            size = (func.end_ea - func.start_ea) if func else 0
            name = idc.get_func_name(ea) or ""
            is_named = 0 if name.startswith("sub_") or not name else 1
            writer.writerow([f"0x{ea:08X}", f"0x{size:X}", name, is_named])
            count += 1
    return count


def export_strings(path: str) -> int:
    count = 0
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["va", "length", "text"])
        for item in idautils.Strings():
            try:
                text = str(item)
            except Exception:
                continue
            writer.writerow([f"0x{item.ea:08X}", item.length, text])
            count += 1
    return count


def export_segments(path: str) -> int:
    count = 0
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "start", "end", "size", "perm"])
        seg = ida_segment.get_first_seg()
        while seg:
            name = ida_segment.get_segm_name(seg)
            writer.writerow([name, f"0x{seg.start_ea:08X}", f"0x{seg.end_ea:08X}",
                             f"0x{seg.end_ea - seg.start_ea:X}", seg.perm])
            seg = ida_segment.get_next_seg(seg.start_ea)
            count += 1
    return count


def main() -> None:
    directory = out_dir()
    functions = export_functions(os.path.join(directory, "function_inventory.csv"))
    strings = export_strings(os.path.join(directory, "string_inventory.csv"))
    segments = export_segments(os.path.join(directory, "segments.csv"))
    print(f"exported: {functions} functions, {strings} strings, {segments} segments -> {directory}")


if __name__ == "__main__":
    main()
