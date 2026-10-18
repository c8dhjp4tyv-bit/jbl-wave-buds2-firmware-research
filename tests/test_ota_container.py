"""Round-trip and parse tests for the OTA container tooling."""
from __future__ import annotations

import os
import zlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ota_repack  # noqa: E402
import ota_unpack  # noqa: E402


def build_synthetic() -> tuple[bytes, bytes]:
    block = ota_repack.BLOCK_SIZE
    pattern = b"JBL-WAVE-BUDS2-synthetic-payload-"
    filler = (pattern * ((7 * block) // len(pattern) + 1))[: 7 * block]
    image = filler + pattern[:1234]
    blocks = [image[i:i + block] for i in range(0, len(image), block)]
    header = b"\xff\xff\xff\xff\x00\x00\x00\x00"
    return image, ota_repack.pack(header, blocks)


class ContainerTests(unittest.TestCase):
    def test_roundtrip_identity(self) -> None:
        image, packed = build_synthetic()
        header, blocks = ota_repack.parse_blocks(packed)
        self.assertEqual(ota_repack.pack(header, blocks), packed)
        self.assertEqual(b"".join(blocks), image)

    def test_unpack_reports(self) -> None:
        _, packed = build_synthetic()
        info = ota_unpack.parse(packed)
        self.assertEqual(info["streams"], 8)
        self.assertEqual(info["stored_crc"], info["calc_crc"])

    def test_real_package_when_available(self) -> None:
        path = os.environ.get("WAVEBUDS_PACKAGE")
        if not path or not Path(path).is_file():
            self.skipTest("set WAVEBUDS_PACKAGE to verify a real package")
        packed = Path(path).read_bytes()
        info = ota_unpack.parse(packed)
        self.assertEqual(info["stored_crc"], info["calc_crc"])
        self.assertEqual(info["streams"], 8)
        header, blocks = ota_repack.parse_blocks(packed)
        self.assertEqual(ota_repack.pack(header, blocks), packed)


    @staticmethod
    def with_crc(body: bytes) -> bytes:
        return body + f"{zlib.crc32(body) & 0xFFFFFFFF:08X}\n".encode("ascii")

    def test_rejects_bad_header_even_with_valid_crc(self) -> None:
        _, packed = build_synthetic()
        with self.assertRaisesRegex(ValueError, "header"):
            ota_unpack.parse(self.with_crc(b"NOT!" + packed[4:-9]))

    def test_rejects_bad_declared_length_even_with_valid_crc(self) -> None:
        _, packed = build_synthetic()
        body = bytearray(packed[:-9])
        original = int.from_bytes(body[4:8], "big")
        body[4:8] = (original + 1).to_bytes(4, "big")
        with self.assertRaises(ValueError):
            ota_unpack.parse(self.with_crc(bytes(body)))

    def test_rejects_data_before_crc_trailer(self) -> None:
        _, packed = build_synthetic()
        body = packed[:-(len(ota_repack.CRC_PREFIX) + 9)] + b"JUNK" + ota_repack.CRC_PREFIX
        with self.assertRaisesRegex(ValueError, "unexpected bytes"):
            ota_unpack.parse(self.with_crc(body))

    def test_rejects_bad_crc(self) -> None:
        _, packed = build_synthetic()
        with self.assertRaisesRegex(ValueError, "CRC"):
            ota_unpack.parse(packed[:-9] + b"00000000\n")

    def test_rejects_oversized_last_block(self) -> None:
        _, packed = build_synthetic()
        header, blocks = ota_repack.parse_blocks(packed)
        blocks[-1] = b"X" * (ota_repack.BLOCK_SIZE + 1)
        with self.assertRaisesRegex(ValueError, "last block"):
            ota_repack.pack(header, blocks)


if __name__ == "__main__":
    unittest.main()
