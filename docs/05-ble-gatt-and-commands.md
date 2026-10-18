# 05 — BLE/GATT, command protocol, and TOTA v2 transport

Two logical channels run over BLE GATT: a simple **command** channel (device
info, settings — no authentication) and the **OTA** transport (BES "TOTA v2",
an encrypted session). Both were exercised live from Linux (BlueZ + `bleak`).
Unit-specific addresses are redacted below.

## Advertising and connection

- BLE name: `JBL Wave Buds 2-LE`; advertises service UUIDs `fe2c` and `fddf`.
- Uses a resolvable/rotating LE address. After the first connect, BlueZ service
  discovery sometimes stalls; `bluetoothctl power off/on`, removing the stale LE
  device, then re-scanning clears it. This is a host-stack quirk, not a device
  fault.

## GATT map

| Service | Characteristic | Properties | Role |
|---|---|---|---|
| `fe2c123x-8366-4814-8eb0-01de32100bea` | `fe2c1233`/`1239` | read | custom control (read) |
| | `fe2c1234`/`1235`/`1237` | write, notify | custom control |
| | `fe2c1236` | write | custom control |
| `65786365-6c70-6f69-6e74-2e636f6d0000` ("excelpoint.com") | `…0002` | write / write-no-resp | **command: app → device** |
| | `…0001` | notify | **command: device → app** |
| `01000100-…-009078563412` (OTA_SERVICE_NORMAL) | `03000300-…` | write | OTA data (unused on this unit) |
| | `02000200-…` | notify | OTA status (unused on this unit) |
| `86868686-8686-…-868686868686` (BES TOTA) | `97979797-9797-…-979797979797` | write-no-resp, write, notify | **OTA transport (the real channel)** |
| `00001800` / `00001801` | — | — | GAP / GATT |

Note the naming in the app's constants for the command service is inverted
relative to the live device: `…0002` is the write (app → device) endpoint and
`…0001` is the notify (device → app) endpoint.

## Command protocol (Harman protocol3) — no auth

Control class `com.harman.cmdctrl.imp.control.u3.protocol3.WaveBuds2Control`.
Basic reads/writes require no authentication (verified live).

```
GET  : [AA][cmd][len_lo][len_hi][01=get][ feat_hi feat_lo ... ]
RET  : [AA][cmd][len_lo][len_hi][02=ret][ feat_hi feat_lo | value ... ]
identifier = 0xAA, device-info cmd = 0x06, feature id is 2 bytes (big-endian)
len = number of bytes after the payload-type byte (LE16)
```

Example — FirmwareVersion (feature `0x000C`):

```
WRITE  …0002:  AA 06 03 00 01 00 0C
NOTIFY …0001:  AA 06 06 00 02 00 0C 02 00 00     → version 2.0.0
```

On connect the device emits an unsolicited "hello" notify containing the model
string `JBL Wave Buds 2`, the PID (`0x2100`), and the unit MAC.

### DeviceInfo features (selected)

| id | Name | Type |
|---|---|---|
| 1 | MTU | u16 |
| 4 | ProductID | u16 |
| 6 | DeviceName | UTF-8 |
| 8 / 9 | L/R SerialNumber | ASCII |
| 10 / 11 | MAC / SecondaryMAC | MAC |
| **12** | **FirmwareVersion** | version string (byte triple joined by `.`) |
| 13 / 14 | L/R Battery | u8 level |
| 24..32 | ANC / Ambient / TalkThru / Adaptive / Leakage / EarCanal / ANCAlwaysOn / AutoComp | u8 |
| 57 | AuthenticateDevice | anti-counterfeit (RSA, see [07](07-app-side-analysis.md)) |

Feature 12 is the version readback that returned `2.0.0` irrespective of OTA
state — see [03](03-firmware-image-layout.md) for why.

## BES TOTA v2 transport (OTA channel)

The OTA session runs on service `86868686…` / characteristic `97979797…`
(`BES_TOTA_SERVICE_OTA_UUID` / `BES_TOTA_CHARACTERISTI_OTA_UUID`). The app
selects it when `DeviceProtocol == BLE` and `isTotaConnect == true`. Raw OTA
opcodes are ignored until the TOTA v2 handshake completes
(`BesOtaService.onDataReceived`: processed only once `totauccess` is set); the
first 4 bytes of every inner frame (`00 90 len16`) are stripped as the TOTA
header. The full handshake and key schedule were reverse-engineered from the app
(`TOTAConnectCMD`, `besFunc`, `aes`, `BesSdkConstants`) and verified live — the
device returned "connect success."

### Outer frame

```
"HEAD"(48454144) + len(LE32) + payload + crc32(payload)(LE32) + "TAIL"(5441494C)
```

During the handshake the payload is cleartext; afterwards the payload is
AES-encrypted. Large data is split into `(mtu − 16)`-byte chunks, each in its own
HEAD…TAIL frame.

### Handshake

```
1) App → START   : 01 10 | LE16(rblen+1) | rblen | random_b[rblen]      (cleartext)
2) Dev → 02 10   | LE16(ralen+1) | .. | random_a                         (status 769)
      hash_key_b = SHA256( besFunc.func1(random_a, random_b) )           (32 bytes)
      aes_key    = besFunc.func(hash_key_b) = bytes [0,2,4,…,30]          (16 bytes, AES-128)
3) App → CONFIRM : 03 10 21 00 20 | hash_key_b[32]                        (cleartext)
4) Dev → 00 10 … "connect success."  (inner[12:15] == "suc")             (status 770 → totauccess)
```

`besFunc.func1(a, b)`: zero-pad the shorter to the longer; for each index `i`,
`op = i % 6` selects `[a+b, a*b, a&b, a|b, a^b, a²+b²]` (all `& 0xFF`).
`besFunc.func(h)`: take every second byte of the 32-byte SHA-256 → 16-byte
AES-128 key.

This matches the decoded app class
`com.harman.bluetooth.ota.spp.utils.sha.besFunc`: `generate_random_algorithm`
selects one of six ops by `i % 6`, `func1` pads and combines, and `func` takes
every second byte. The key schedule in [`tools/tota_v2.py`](../tools/tota_v2.py)
is the app's own algorithm, confirmed from its smali.

### AES

`AES/CBC/NoPadding`, IV = `00 01 02 … 0f`, plaintext zero-padded to a multiple of
16.

### Inner command framing

```
convertToTotaCMD(inner) = 00 90 | LE16(len) | inner
inner = [opcode] + [LE16(bodyLen) if USER_FLAG==1] + body     (body may begin with "BEST")
```

`USER_FLAG` starts at 0 (no length field); after `setOtaUser` (0x97) is accepted
it becomes 1 (length field present). On this unit the device accepts the OTA
command opcodes with `USER_FLAG == 0` (opcode immediately followed by
`"BEST"`/payload).

### Key point

The entire key schedule is derived **client-side** from two random nonces; there
is no server- or device-held secret. The transport encryption therefore protects
the link, not the authenticity of the image — consistent with
[04](04-security-model.md). The command generators and the full send sequence are
in [06](06-ota-protocol.md).
