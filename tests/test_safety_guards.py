"""Safety guards must stay active under optimized Python (`python -O`).

These run the tools in a subprocess with `-O` so that any guard implemented with
`assert` (which `-O` strips) would be caught as a regression.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRC = ROOT / "tools" / "crc_check.py"
REPACK = ROOT / "tools" / "ota_repack.py"


class OptimizedModeSafetyTests(unittest.TestCase):
    def run_o(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-O", *args], cwd=ROOT, check=False, capture_output=True, text=True
        )

    def test_crc_selftest_passes_under_optimized(self) -> None:
        result = self.run_o(str(CRC), "--selftest")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("selftest: OK", result.stdout)

    def test_crc_mismatch_fails_under_optimized(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as handle:
            handle.write(b"payload" + b"CRC32_OF_IMAGE=0x" + b"DEADBEEF\n")
            path = handle.name
        result = self.run_o(str(CRC), path)
        self.assertNotEqual(result.returncode, 0)

    def test_repack_rejects_non_package_under_optimized(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as handle:
            handle.write(b"not an OTA package")
            path = handle.name
        result = self.run_o(str(REPACK), "inspect", path)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
