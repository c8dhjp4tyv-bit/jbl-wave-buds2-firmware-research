"""Tests for the structural factory-table locator."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_factory_table as E  # noqa: E402


def va_for_offset(offset: int) -> int:
    # Inverse of E.va_to_off for the default base: off = (va & 0xFFFFFF) - 0x10000.
    return (E.IMAGE_BASE & 0xFF000000) | (offset + 0x10000)


def synth_image() -> bytes:
    size = 0x8000
    buf = bytearray(size)
    names = [b"CIDR\x00", b"SETMACADDR,\x00", b"GETTRIM\x00", b"LINKKEY\x00", b"ANC,\x00"]
    name_off, name_vas = 0x1000, []
    off = name_off
    for name in names:
        buf[off:off + len(name)] = name
        name_vas.append(va_for_offset(off))
        off += len(name)
    table_off = 0x2000
    for i, name_va in enumerate(name_vas):
        handler_va = va_for_offset(0x800 + i * 0x40)  # plausible code pointer
        entry = struct.pack("<II", handler_va, name_va)
        buf[table_off + i * 8: table_off + i * 8 + 8] = entry
    return bytes(buf)


class FactoryTableTests(unittest.TestCase):
    def test_locates_and_resolves(self) -> None:
        rows = E.extract(synth_image(), E.IMAGE_BASE, min_run=5)
        commands = [r["command"] for r in rows]
        self.assertEqual(commands, ["CIDR", "SETMACADDR", "GETTRIM", "LINKKEY", "ANC"])
        self.assertEqual(rows[1]["takes_arg"], 1)  # "SETMACADDR," takes an argument
        self.assertEqual(rows[0]["takes_arg"], 0)


if __name__ == "__main__":
    unittest.main()
