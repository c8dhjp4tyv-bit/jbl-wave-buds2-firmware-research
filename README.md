# JBL Wave Buds 2 — Firmware & OTA Reverse Engineering

Reverse engineering of the JBL Wave Buds 2 (Bestechnic BES1306) firmware and
over-the-air update path: the on-flash layout, the OTA container format down to
the byte, the BLE/GATT command protocol and the BES "TOTA v2" encrypted
transport, the device- and app-side trust boundaries, and a reproducible method
for loading a self-built firmware image onto a unit you own.

I could find no prior public teardown of this specific model; corrections and
additions are welcome.

## What this is — and isn't

- It **is** original documentation, analysis, and tooling, with every format
  claim checked by a parser that round-trips the official package byte-for-byte.
- It **does not** redistribute any JBL/Harman firmware binary, decompiled image,
  or application code. The tools operate on artifacts you obtain from your own
  device and from JBL's public server.
- All work was done on the author's own hardware. See
  [SECURITY.md](SECURITY.md) for the disclosure position.

## Key findings

| # | Finding |
|---|---|
| 1 | The OTA image is **not cryptographically signed** — integrity is CRC-32 only. A CRC-valid image with one modified byte was accepted and booted. |
| 2 | The app's RSA-2048 verifier is **anti-counterfeit** (device authenticity), not firmware signing. |
| 3 | The companion app does **not pin** its OTA endpoints; a user CA is enough to intercept OTA traffic. |
| 4 | OTA is **staged** — the download phase is brick-safe; the risk window is post-reboot activation. |
| 5 | An external BLE central **cannot drive** OTA: the device accept path is gated on an internal TWS/connection state. |
| 6 | The BES TOTA v2 transport uses a **client-derived AES-128 session key** — no server/device secret. |

Details and evidence are in [`docs/`](docs/).

## Documentation

| | |
|---|---|
| [00 — Overview](docs/00-overview.md) | device, methodology, findings, scope |
| [01 — Hardware & flash map](docs/01-hardware-flash-map.md) | BES1306, 2 MB NOR layout |
| [02 — OTA container format](docs/02-ota-container-format.md) | byte-level format + CRC recipe |
| [03 — Firmware image layout](docs/03-firmware-image-layout.md) | decompressed image structure |
| [04 — Security model](docs/04-security-model.md) | what is and isn't verified |
| [05 — BLE/GATT & commands](docs/05-ble-gatt-and-commands.md) | GATT map, protocol3, TOTA v2 |
| [06 — OTA protocol](docs/06-ota-protocol.md) | command set, sequence, the accept gate |
| [07 — App-side analysis](docs/07-app-side-analysis.md) | config path, RSA verifier, no pinning |
| [08 — Delivery method](docs/08-delivery-method.md) | reproducible owner-device method |
| [09 — Function catalogue](docs/09-function-catalog.md) | IDA functions by module |
| [10 — Factory console](docs/10-factory-console.md) | verified 59-command engineering console |

## Tools

Format tooling that operates on **your own** copy of the official package:

```
python3 tools/ota_unpack.py  <official_package.bin>          # parse + report
python3 tools/crc_check.py   <official_package.bin>          # verify the trailer CRC-32
python3 tools/ota_repack.py  inspect   <official_package.bin>
python3 tools/ota_repack.py  make-test <official_package.bin> <out.bin>
```

See [docs/08-delivery-method.md](docs/08-delivery-method.md) for the full method
(app patch + config interception) and [`tools/`](tools/) for the capture add-on
and build helper.

## Environment

- Static analysis: IDA 9.4 (Hex-Rays), decompressed image at base `0x2C010000`.
- App: `apktool` / `androguard`.
- Live device: Linux BlueZ + `bleak`; `mitmproxy` with a user CA.

## Caution

Flashing firmware is irreversible and there is no exposed recovery path. A
CRC-valid but functionally broken image will still activate. Validate the
pipeline with the **unmodified** official image first, and only derive images
from the **current** official package for your unit. You do this at your own risk.

## License

Code under [MIT](LICENSE); documentation under CC-BY-4.0. See [LICENSE](LICENSE).
To cite this work, see [CITATION.cff](CITATION.cff).
