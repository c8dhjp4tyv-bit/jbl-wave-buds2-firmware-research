#!/usr/bin/env python3
"""Read-only BLE/GATT query for the JBL Wave Buds 2 (Linux BlueZ + bleak).

Connects over the protocol3 command service and reads device info
(firmware version, product id, serial, battery). It only reads — it never
writes to flash. Protocol reference: docs/05-ble-gatt-and-commands.md.

    pip install bleak
    python3 ble_query.py                 # scan by name
    python3 ble_query.py <BLE-ADDRESS>   # connect by address
"""
from __future__ import annotations

import asyncio
import sys

from bleak import BleakClient, BleakScanner

COMMAND_SERVICE = "65786365-6c70-6f69-6e74-2e636f6d0000"
WRITE_CHAR = "65786365-6c70-6f69-6e74-2e636f6d0002"   # app -> device
NOTIFY_CHAR = "65786365-6c70-6f69-6e74-2e636f6d0001"  # device -> app
NAME_HINTS = ("jbl", "wave", "buds")


def protocol3_get(command: int, features: list[int]) -> bytes:
    body = [0x01]
    for feature in features:
        body += [(feature >> 8) & 0xFF, feature & 0xFF]
    return bytes([0xAA, command, len(body) & 0xFF, (len(body) >> 8) & 0xFF] + body)


REQUESTS = {
    "FirmwareVersion": protocol3_get(0x06, [12]),
    "ProductID": protocol3_get(0x06, [4]),
    "Serial(L/R)": protocol3_get(0x06, [8, 9]),
    "Battery(L/R)": protocol3_get(0x06, [13, 14]),
}


def _ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def _on_notify(_: object, data: bytearray) -> None:
    print(f"  << {data.hex()} | {_ascii(bytes(data))}")


async def main() -> None:
    address = sys.argv[1] if len(sys.argv) > 1 else None
    if not address:
        print("scanning for 12 s …")
        devices = await BleakScanner.discover(timeout=12.0, return_adv=True)
        for _, (device, adv) in devices.items():
            name = (adv.local_name or device.name or "")
            if any(hint in name.lower() for hint in NAME_HINTS) or COMMAND_SERVICE in [
                u.lower() for u in (adv.service_uuids or [])
            ]:
                address = device.address
                print(f"  selected {address} ({name})")
                break
        if not address:
            print("no JBL/Wave/Buds device found. Take the buds out of the case and close the phone app.")
            return

    client = BleakClient(address, timeout=30.0)
    await client.connect()
    if not client.is_connected:
        print("could not connect.")
        return
    try:
        await client.start_notify(NOTIFY_CHAR, _on_notify)
        for name, request in REQUESTS.items():
            print(f">> {name}: {request.hex()}")
            try:
                await client.write_gatt_char(WRITE_CHAR, request, response=True)
            except Exception as error:  # noqa: BLE001 - report and continue
                print(f"   write failed ({name}): {error!r}")
            await asyncio.sleep(1.2)
        await asyncio.sleep(2.0)
    finally:
        await client.disconnect()
    print("done (read-only; nothing was written).")


if __name__ == "__main__":
    asyncio.run(main())
