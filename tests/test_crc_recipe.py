"""Tests for the container CRC-32 recipe."""
from __future__ import annotations

import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import crc_check  # noqa: E402


class CrcRecipeTests(unittest.TestCase):
    def test_recipe_roundtrip(self) -> None:
        body = b"payload-bytes" + crc_check.PREFIX
        crc = zlib.crc32(body) & 0xFFFFFFFF
        package = body + f"{crc:08X}\n".encode("ascii")
        stored, calculated, cut = crc_check.check(package)
        self.assertEqual(stored, calculated)
        self.assertEqual(stored, crc)
        self.assertEqual(cut, len(body))

    def test_detects_mismatch(self) -> None:
        package = b"payload" + crc_check.PREFIX + b"DEADBEEF\n"
        stored, calculated, _ = crc_check.check(package)
        self.assertNotEqual(stored, calculated)


if __name__ == "__main__":
    unittest.main()
