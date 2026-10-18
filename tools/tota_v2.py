#!/usr/bin/env python3
"""BES "TOTA v2" transport — reference implementation.

Documents the encrypted OTA transport of the JBL Wave Buds 2 in runnable form:
the handshake, the client-side key schedule, AES-128-CBC framing, the inner
command framing, and the OTA command builders. Protocol reference: docs/05 and
docs/06.

Completing the handshake is necessary but NOT sufficient to drive OTA: the
device gates its OTA command handlers on an internal TWS/connection state
(docs/06), so an external central can establish the session and read versions
but cannot push an image on its own. This file is a protocol reference; real
image delivery goes through the companion app (docs/08).

    pip install bleak cryptography
    python3 tota_v2.py        # connect, handshake, read protocol + current version
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import struct
import zlib

HEAD, TAIL = b"HEAD", b"TAIL"
MAGIC = b"BEST"
TOTA_INNER = bytes([0x00, 0x90])
AES_IV = bytes(range(16))
# Local reference-tool limit, not a measured maximum supported by the device.
MAX_TOTA_PAYLOAD = 64 * 1024

TOTA_CHAR = "97979797-9797-9797-9797-979797979797"
NAME_HINTS = ("jbl", "wave", "buds")


# --- key schedule (besFunc) ---------------------------------------------------
def bf_gen(i: int, a: int, b: int) -> int:
    a &= 0xFF
    b &= 0xFF
    return [a + b, a * b, a & b, a | b, a ^ b, a * a + b * b][i % 6] & 0xFF


def bf_func1(a: bytes, b: bytes) -> bytes:
    a, b = bytearray(a), bytearray(b)
    if len(a) > len(b):
        b += bytearray(len(a) - len(b))
    elif len(b) > len(a):
        a += bytearray(len(b) - len(a))
    return bytes(bf_gen(i, a[i], b[i]) for i in range(len(a)))


def bf_func(h: bytes) -> bytes:
    """Every second byte of the 32-byte SHA-256 -> 16-byte AES-128 key."""
    return bytes(h[i * 2] for i in range(16))


# --- AES-128-CBC / NoPadding --------------------------------------------------
def _aes_encrypt(data: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    c = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).encryptor()
    return c.update(data) + c.finalize()


def _aes_decrypt(data: bytes, key: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    c = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).decryptor()
    return c.update(data) + c.finalize()


def _zpad16(b: bytes) -> bytes:
    r = len(b) % 16
    return b if r == 0 else b + bytes(16 - r)


# --- framing ------------------------------------------------------------------
def _crc32(b: bytes) -> int:
    return zlib.crc32(b) & 0xFFFFFFFF


def _le16(n: int) -> bytes:
    return struct.pack("<H", n & 0xFFFF)


def _le32(n: int) -> bytes:
    return struct.pack("<I", n & 0xFFFFFFFF)


def tota_wrap(payload: bytes) -> bytes:
    if len(payload) > MAX_TOTA_PAYLOAD:
        raise ValueError(f"TOTA payload exceeds {MAX_TOTA_PAYLOAD} bytes")
    return HEAD + _le32(len(payload)) + payload + _le32(_crc32(payload)) + TAIL


def tota_unwrap(buf: bytes) -> tuple[list[bytes], bytes]:
    """Decode CRC-valid frames, retaining only a possible incomplete frame.

    Bad CRCs, tails, and oversized lengths are discarded while searching for
    the next HEAD. A valid-looking incomplete frame is retained intact, since
    HEAD can also occur inside a payload. Retained data is bounded by the local
    payload limit plus 15 framing bytes. CRC detects corruption, not forgery.
    """
    out: list[bytes] = []
    i = 0
    while True:
        h = buf.find(HEAD, i)
        if h < 0:
            # Preserve a split magic marker, but never accumulate arbitrary noise.
            for size in range(min(len(HEAD) - 1, len(buf) - i), 0, -1):
                if buf.endswith(HEAD[:size]):
                    return out, buf[-size:]
            return out, b""
        if len(buf) < h + 8:
            return out, buf[h:]
        length = struct.unpack_from("<I", buf, h + 4)[0]
        if length > MAX_TOTA_PAYLOAD:
            i = h + 1
            continue
        payload_end = h + 8 + length
        end = payload_end + 4 + len(TAIL)
        if len(buf) < end:
            return out, buf[h:]
        payload = buf[h + 8:payload_end]
        stored_crc = struct.unpack_from("<I", buf, payload_end)[0]
        if buf[payload_end + 4:end] != TAIL or stored_crc != _crc32(payload):
            i = h + 1
            continue
        out.append(payload)
        i = end


def to_inner(cmd: bytes) -> bytes:
    return TOTA_INNER + _le16(len(cmd)) + cmd


# --- OTA command builders (USER_FLAG == 0 form; see docs/06) ------------------
def cmd_proto(legacy: int = 0) -> bytes:
    return to_inner(bytes([0x99, 0, 0, 0, legacy]))


def cmd_curver() -> bytes:
    return to_inner(bytes([0x8E]) + MAGIC)


def cmd_setuser(user: int = 1) -> bytes:
    return to_inner(bytes([0x97, user & 0xFF]))


def cmd_start(image: bytes) -> bytes:
    return to_inner(bytes([0x80]) + MAGIC + _le32(len(image)) + _le32(_crc32(image)))


# --- session ------------------------------------------------------------------
class TotaSession:
    def __init__(self) -> None:
        self.random_b = b""
        self.aes_key = b""
        self.connected = False
        self._hash_key_b = b""
        self._buf = b""

    def start(self) -> bytes:
        self.aes_key = b""
        self._hash_key_b = b""
        self.connected = False
        self._buf = b""
        n = random.randint(16, 127)
        self.random_b = bytes(random.getrandbits(8) for _ in range(n))
        return tota_wrap(bytes([0x01, 0x10]) + _le16(n + 1) + bytes([n]) + self.random_b)

    def on_handshake(self, inner: bytes) -> int:
        if inner.startswith(b"\x02\x10"):
            if len(inner) < 5 or not self.random_b:
                return 0
            declared_length = struct.unpack_from("<H", inner, 2)[0]
            if declared_length <= 1 or len(inner) != 4 + declared_length:
                return 0
            random_a = inner[5:]
            self._hash_key_b = hashlib.sha256(bf_func1(random_a, self.random_b)).digest()
            self.aes_key = bf_func(self._hash_key_b)
            return 769
        if (self.aes_key and len(inner) >= 15 and inner[:2] == b"\x00\x10"
                and inner[12:15] == b"suc"):
            self.connected = True
            return 770
        return 0

    def confirm(self) -> bytes:
        return tota_wrap(bytes([0x03, 0x10, 0x21, 0x00, 0x20]) + self._hash_key_b)

    def wrap(self, inner_cmd: bytes) -> bytes:
        return tota_wrap(_aes_encrypt(_zpad16(inner_cmd), self.aes_key))

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames, self._buf = tota_unwrap(self._buf)
        return frames


async def _demo() -> None:
    from bleak import BleakClient, BleakScanner

    target = None
    for _ in range(4):
        for _, (device, adv) in (await BleakScanner.discover(timeout=10.0, return_adv=True)).items():
            name = (adv.local_name or device.name or "").lower()
            if any(hint in name for hint in NAME_HINTS):
                target = device
                break
        if target:
            break
    if not target:
        print("device not found")
        return

    session = TotaSession()
    event = asyncio.Event()

    def on_notify(_: object, data: bytearray) -> None:
        for frame in session.feed(bytes(data)):
            if not session.connected:
                if session.on_handshake(frame) in (769, 770):
                    event.set()
            else:
                inner = _aes_decrypt(frame, session.aes_key)
                print(f"  << {inner[4:].hex()}")

    client = BleakClient(target, timeout=20.0)
    await client.connect()
    try:
        await client.start_notify(TOTA_CHAR, on_notify)
        await client.write_gatt_char(TOTA_CHAR, session.start(), response=False)
        await asyncio.wait_for(event.wait(), 8.0)
        event.clear()
        await client.write_gatt_char(TOTA_CHAR, session.confirm(), response=False)
        await asyncio.wait_for(event.wait(), 8.0)
        if not session.connected:
            print("handshake did not complete")
            return
        print("TOTA v2 session established")
        for cmd, label in ((cmd_proto(), "getProtocolVersion"), (cmd_curver(), "getCurrentVersion")):
            print(f">> {label}")
            await client.write_gatt_char(TOTA_CHAR, session.wrap(cmd), response=False)
            await asyncio.sleep(1.5)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(_demo())
