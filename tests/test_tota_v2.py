"""TOTA transport regression tests; no firmware, BLE adapter, or AES dependency."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import tota_v2 as tota  # noqa: E402


# CRC-32("123456789") = 0xCBF43926, encoded little-endian on the wire.
KNOWN_PAYLOAD = b"123456789"
KNOWN_FRAME = b"HEAD\x09\x00\x00\x00123456789\x26\x39\xf4\xcbTAIL"
CHALLENGE = b"\x02\x10\x11\x00\x10" + b"A" * 16
SUCCESS = b"\x00\x10\x10\x00connect success."


class FramingTests(unittest.TestCase):
    def test_decodes_known_wire_vector(self) -> None:
        self.assertEqual(tota.tota_unwrap(KNOWN_FRAME), ([KNOWN_PAYLOAD], b""))

    def test_wrap_matches_known_wire_vector(self) -> None:
        self.assertEqual(tota.tota_wrap(KNOWN_PAYLOAD), KNOWN_FRAME)

    def test_empty_payload(self) -> None:
        wire = b"HEAD" + bytes(8) + b"TAIL"
        self.assertEqual(tota.tota_unwrap(wire), ([b""], b""))

    def test_rejects_bad_crc(self) -> None:
        wire = bytearray(KNOWN_FRAME)
        wire[-8] ^= 1
        self.assertEqual(tota.tota_unwrap(bytes(wire)), ([], b""))

    def test_rejects_bad_tail(self) -> None:
        self.assertEqual(tota.tota_unwrap(KNOWN_FRAME[:-4] + b"FAIL"), ([], b""))

    def test_rejects_corrupted_payload(self) -> None:
        wire = bytearray(KNOWN_FRAME)
        wire[8] ^= 1
        self.assertEqual(tota.tota_unwrap(bytes(wire)), ([], b""))

    def test_all_two_part_fragment_boundaries(self) -> None:
        for split in range(1, len(KNOWN_FRAME)):
            with self.subTest(split=split):
                session = tota.TotaSession()
                self.assertEqual(session.feed(KNOWN_FRAME[:split]), [])
                self.assertEqual(session.feed(KNOWN_FRAME[split:]), [KNOWN_PAYLOAD])
                self.assertEqual(session._buf, b"")

    def test_multiple_frames_with_garbage(self) -> None:
        wire = b"noise" + KNOWN_FRAME + b"junk" + tota.tota_wrap(b"second")
        self.assertEqual(tota.tota_unwrap(wire), ([KNOWN_PAYLOAD, b"second"], b""))

    def test_recovers_after_malformed_frame(self) -> None:
        bad_crc = bytearray(KNOWN_FRAME)
        bad_crc[-8] ^= 1
        for bad in (bytes(bad_crc), KNOWN_FRAME[:-4] + b"FAIL"):
            with self.subTest(wire=bad):
                self.assertEqual(tota.tota_unwrap(bad + KNOWN_FRAME), ([KNOWN_PAYLOAD], b""))

    def test_recovers_after_oversized_declared_length(self) -> None:
        for length in (tota.MAX_TOTA_PAYLOAD + 1, 0xFFFFFFFF):
            with self.subTest(length=length):
                bad_header = b"HEAD" + struct.pack("<I", length)
                self.assertEqual(
                    tota.tota_unwrap(bad_header + KNOWN_FRAME), ([KNOWN_PAYLOAD], b"")
                )

    def test_noise_buffer_stays_bounded(self) -> None:
        session = tota.TotaSession()
        for _ in range(3):
            self.assertEqual(session.feed(b"x" * 8192), [])
            self.assertEqual(session._buf, b"")

    def test_preserves_partial_magic(self) -> None:
        for size in range(1, len(tota.HEAD)):
            with self.subTest(size=size):
                session = tota.TotaSession()
                self.assertEqual(session.feed(b"noise" + KNOWN_FRAME[:size]), [])
                self.assertEqual(session._buf, KNOWN_FRAME[:size])
                self.assertEqual(session.feed(KNOWN_FRAME[size:]), [KNOWN_PAYLOAD])

    def test_discards_noise_before_incomplete_frame(self) -> None:
        self.assertEqual(tota.tota_unwrap(b"noise" + KNOWN_FRAME[:10]), ([], KNOWN_FRAME[:10]))

    def test_does_not_resync_inside_partial_payload(self) -> None:
        payload = b"prefix" + KNOWN_FRAME + b"suffix"
        wire = tota.tota_wrap(payload)
        session = tota.TotaSession()
        self.assertEqual(session.feed(wire[:-1]), [])
        self.assertEqual(session._buf, wire[:-1])
        self.assertEqual(session.feed(wire[-1:]), [payload])

    def test_stream_in_small_chunks(self) -> None:
        bad = KNOWN_FRAME[:-4] + b"FAIL"
        wire = b"garbage" + bad + KNOWN_FRAME + tota.tota_wrap(b"next") + b"HE"
        for size in (1, 2, 3, 7, 16, 64):
            with self.subTest(chunk_size=size):
                session = tota.TotaSession()
                frames = []
                for offset in range(0, len(wire), size):
                    frames.extend(session.feed(wire[offset:offset + size]))
                self.assertEqual(frames, [KNOWN_PAYLOAD, b"next"])
                self.assertEqual(session._buf, b"HE")

    def test_accepts_payload_at_limit_and_bounds_incomplete_buffer(self) -> None:
        payload = b"x" * tota.MAX_TOTA_PAYLOAD
        wire = tota.tota_wrap(payload)
        session = tota.TotaSession()
        self.assertEqual(session.feed(b"noise" + wire[:-1]), [])
        self.assertLessEqual(len(session._buf), tota.MAX_TOTA_PAYLOAD + 15)
        self.assertEqual(session.feed(wire[-1:]), [payload])
        self.assertEqual(session._buf, b"")

    def test_rejects_payload_over_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "payload"):
            tota.tota_wrap(b"x" * (tota.MAX_TOTA_PAYLOAD + 1))


class HandshakeTests(unittest.TestCase):
    def test_truncated_or_inconsistent_challenges_do_not_change_keys(self) -> None:
        malformed = [
            b"\x02\x10",
            b"\x02\x10\x11",
            b"\x02\x10\x11\x00",
            b"\x02\x10\x00\x00\x00",
            b"\x02\x10\x01\x00\x00",
            CHALLENGE[:-1],
            CHALLENGE + b"extra",
        ]
        for inner in malformed:
            with self.subTest(inner=inner):
                session = tota.TotaSession()
                session.random_b = b"B" * 16
                self.assertEqual(session.on_handshake(inner), 0)
                self.assertEqual(session.aes_key, b"")
                self.assertEqual(session._hash_key_b, b"")
                self.assertFalse(session.connected)

    def test_challenge_requires_started_session(self) -> None:
        session = tota.TotaSession()
        self.assertEqual(session.on_handshake(CHALLENGE), 0)
        self.assertEqual(session.aes_key, b"")

    def test_valid_challenge_derives_known_key(self) -> None:
        session = tota.TotaSession()
        session.random_b = b"B" * 16
        self.assertEqual(session.on_handshake(CHALLENGE), 769)
        self.assertEqual(
            session._hash_key_b.hex(),
            "c050796c04a48e827b54913d6b0d464a9f70386aa84bf8730cc435e1b25c86a1",
        )
        self.assertEqual(session.aes_key.hex(), "c079048e7b916b469f38a8f80c35b286")
        self.assertFalse(session.connected)

    def test_success_requires_derived_key(self) -> None:
        session = tota.TotaSession()
        session.start()
        self.assertEqual(session.on_handshake(SUCCESS), 0)
        self.assertFalse(session.connected)

    def test_success_after_challenge_connects(self) -> None:
        session = tota.TotaSession()
        session.random_b = b"B" * 16
        session.on_handshake(CHALLENGE)
        self.assertEqual(session.on_handshake(SUCCESS), 770)
        self.assertTrue(session.connected)

    def test_start_resets_session(self) -> None:
        session = tota.TotaSession()
        session.random_b = b"B" * 16
        session.on_handshake(CHALLENGE)
        session.on_handshake(SUCCESS)
        session.feed(b"HE")
        start = session.start()
        self.assertFalse(session.connected)
        self.assertEqual(session.aes_key, b"")
        self.assertEqual(session._hash_key_b, b"")
        self.assertEqual(session._buf, b"")
        frames, rest = tota.tota_unwrap(start)
        self.assertEqual(rest, b"")
        self.assertEqual(frames[0][5:], session.random_b)


if __name__ == "__main__":
    unittest.main()
