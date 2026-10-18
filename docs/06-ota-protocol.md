# 06 — OTA protocol and the acceptance gate

This chapter covers the BES OTA command set carried inside the TOTA v2 transport
([05](05-ble-gatt-and-commands.md)), the send sequence, and the device-side gate
that stops an external BLE central from driving OTA directly.

## Command set

Inner opcodes (wrapped as `convertToTotaCMD`, then AES-encrypted in-session):

| Command | Opcode | Body |
|---|---|---|
| getProtocolVersion | `0x99` | `00 00 00 <legacy>` |
| getCurrentVersion | `0x8E` | `"BEST"` |
| setOtaUser | `0x97` | `<user=1>` → sets `USER_FLAG` |
| setUpgradeType | `0x9D` | `<1=fast / 2 / 0=normal>` |
| selectSide | `0x90` | `<side>` (TWS L/R) |
| checkBreakPoint | `0x8C` | `"BEST"` + 36 B (resume = 0) |
| OTAConfigure | `0x86` | 92 B: `LE32(88) + imageCRC(img[-4:]) + flags(4=0) + btName(32) + bleName(32) + btAddr(6) + bleAddr(6) + crc32(first 88)` |
| startOTA | `0x80` | `"BEST" + LE32(imageSize) + LE32(crc32(image))` |
| dataPacket | `0x85` | raw image chunk |
| segmentCRC | `0x82` | `"BEST" + LE32(crc32(segment))` every 16384 B |
| imageOverwriteConfirm | `0x92` | `"BEST"` |

Device→app status codes (internal `B_xx` → app `23xx`): `2305` setOtaUser,
`2308/2309` upgradeType, `2311` side, `2312/2313` breakpoint, `2320` config OK,
`2322` data, `2324` segment-CRC OK, `2326` whole-image-CRC OK, `2327`
overwrite-confirm; errors `2368` start, `2370` config, `2371` segment-CRC,
`2372` whole-image-CRC, `2373` overwrite.

Every integrity value in this set is CRC-32 (per-segment and whole-image); there
is no hash or signature — consistent with [04](04-security-model.md).

## Send sequence

```
1  getProtocolVersion (0x99)
2  getCurrentVersion   (0x8E)
3  setOtaUser          (0x97)          → USER_FLAG = 1
4  setUpgradeType      (0x9D)
5  selectSide          (0x90)
6  checkBreakPoint     (0x8C)          → resume offset if any
7  OTAConfigure        (0x86)          → image size + CRC + config
8  startOTA            (0x80)
9  loop: dataPacket (0x85) … periodic segmentCRC (0x82) every 16384 B
10 imageOverwriteConfirm (0x92)
11 device validates whole-image CRC-32 → reboot / activate
```

## Device-side validation (what the handler checks)

`sub_2C0918BC` was decompiled; its opcode dispatch and checks are:

| Opcode | Handler action | Integrity check |
|---|---|---|
| `0x80` startOTA | records image size and expected CRC-32 | `"BEST"` magic (`0x54534542`) |
| `0x86` OTAConfigure | enforces config length (92) and config CRC-32 over the first 88 bytes | CRC-32 (`sub_2C0CE944`) |
| `0x82` segmentCRC | compares a running CRC-32 of received data to the expected value | CRC-32 after `"BEST"` |
| `0x85` dataPacket | writes the chunk into the staging buffer / flash | none |
| `0x92` imageOverwriteConfirm | sets the activation flag `MEMORY[0x200274F4] = 1` once the whole-image CRC matches | CRC-32 |

The integrity primitive throughout is `sub_2C0CE944`, a table-driven CRC-32
(table at `0x2C0F5218`). No signature or hash appears anywhere in the handler —
device-side confirmation of the security model in [04](04-security-model.md).
In the 2.9.0 build the same handler is `sub_2C0918EC` and the CRC routine
`sub_2C0CF480` (table `0x2C0F5BC0`), with identical logic — see
[`generated/cross_build_map.csv`](generated/cross_build_map.csv).

## The acceptance gate (why an external central stalls)

Completing the TOTA v2 handshake is necessary but **not sufficient**. The
device-side OTA command handlers are guarded by a state predicate:

```c
// sub_2C0905E4
BOOL ota_state_ready()
{
    return MEMORY[0x20026BA0] == 2 || MEMORY[0x20026BA0] == 4;
}
```

This predicate is referenced throughout the OTA command-handler cluster — the
main handler `sub_2C0918BC` (0x622 bytes) and relatives `sub_2C091488`,
`sub_2C0911B4`, `sub_2C091EE0`, `sub_2C091300`, `sub_2C0909A8` (18 call sites in
total). The state variable `0x20026BA0` takes the accepting values (2 or 4) only
in the device's normal paired/TWS operating states, which are established through
the ordinary connection flow the companion app participates in — not something an
external BLE central can set on its own.

Observed consequence: a standalone central can establish the encrypted TOTA v2
session and get replies to `setOtaUser` / `getProtocolVersion`, but `OTAConfigure`
/ `startOTA` are dropped while the state variable is outside {2, 4}. The companion
app, running in the normal connected state, is not subject to this stall — which
is why delivery goes through the app ([08](08-delivery-method.md)) rather than a
from-scratch external flasher.

## Staging and brick-safety

The new image is written to the staging region (`0x120000`+) while the running
application (`0x010000`+) is untouched, so the transfer itself is brick-safe. The
risk is the post-reboot activation copy of a CRC-valid-but-broken image; see
[01](01-hardware-flash-map.md) and [04](04-security-model.md).
