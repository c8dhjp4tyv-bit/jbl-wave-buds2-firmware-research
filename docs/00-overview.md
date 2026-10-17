# 00 — Overview

The JBL Wave Buds 2 is a true-wireless earbud set built on a Bestechnic
BES1306 SoC. This repository documents its over-the-air (OTA) update path end
to end: the on-flash layout, the OTA container format, the BLE/GATT command and
OTA transport, the device- and app-side trust boundaries, and a reproducible
method for loading a self-built firmware image onto a unit you own.

All work was performed on hardware owned by the author. No JBL/Harman firmware
binary, no decompiled image, and no proprietary application code is
redistributed here. The repository contains original documentation, analysis,
and tooling that operate on artifacts the reader obtains from their own device
and from JBL's public OTA server. See [SECURITY.md](../SECURITY.md) for the
disclosure position.

## Device under test

| Property | Value |
|---|---|
| Product | JBL Wave Buds 2 |
| SoC | Bestechnic BES1306 (ARMv8-M / Cortex-M33 class, TrustZone-M present) |
| RTOS | Keil RTX5 |
| BT vendor / product | `0x0ECB` (Bestechnic) / `0x2100` — referred to as "PID 2100" |
| modalias | `v0ECBp2100d001F` |
| Build (2.9.0 image) | `BUILD_DATE=Apr 22 2025 15:36:42`, `REV_INFO=d30e8f1:best1306_ibrt_anc` |

Unit-specific identifiers (BT/BLE MAC, serial numbers) are redacted in examples;
they are the author's unit and carry no analytical value.

## Firmware analyzed

The reference image throughout is the official 2.9.0 package
`COMPRESS_WAVE_BUDS2_OTA2_V2.9.0_56e441_20260918.bin` (549,558 bytes,
MD5 `91cd9ade57c67ddc05ba993c82e1cf53`), served by JBL's OTA server for PID 2100.
Its decompressed application image is 955,596 bytes. Static analysis was done in
IDA 9.4 (Hex-Rays) with image base `0x2C010000` (7960 functions).

## Key findings

| # | Finding | Basis |
|---|---|---|
| 1 | The OTA image is **not cryptographically signed**; integrity is CRC32 only. | No RSA/ECDSA/SHA/HMAC strings or routines exist in the application image; the container carries only a CRC32 trailer; a CRC-valid image with a single modified byte was accepted and booted. |
| 2 | The app's RSA-2048 verifier is **anti-counterfeit** (device authenticity), not firmware signing. | `com.jbl.counterfeit.Rsa2048DynamicVerifier`; the `AuthenticateDevice` device-info feature. |
| 3 | The companion app does **not pin** its OTA endpoints. | No `CertificatePinner` configured; adding a user CA via `network_security_config` is sufficient to intercept OTA traffic. |
| 4 | OTA is **staged**; the download phase is brick-safe. | `sub_2C092014` copies into flash at base `0x28120000` (offset `0x120000`) while the running application at `0x010000` is untouched during transfer. |
| 5 | An external BLE central **cannot drive** the device OTA because the accept path is gated on an internal TWS/connection state. | The OTA handlers require `MEMORY[0x20026BA0]` ∈ {2, 4} (`sub_2C0905E4`, 18 call sites); see [06-ota-protocol.md](06-ota-protocol.md). |
| 6 | The BES "TOTA v2" transport uses a **client-derived AES-128 session key**; no server/device secret is involved. | Handshake and key schedule reproduced and verified live; see [05-ble-gatt-and-commands.md](05-ble-gatt-and-commands.md). |
| 7 | The device-side OTA handler confirms **CRC-32-only** integrity. | `sub_2C0918BC` validates config/segment/whole-image with CRC-32 (`sub_2C0CE944`) and a `"BEST"` magic; no signature or hash; see [04-security-model.md](04-security-model.md). |

## Methodology

- Firmware: static analysis of the decompressed 2.9.0 image in IDA 9.4 / Hex-Rays.
- Companion app: `apktool` / `androguard` on the JBL Headphones Android app.
- Live device: Linux BlueZ + `bleak` for BLE/GATT; `mitmproxy` with a user CA for OTA-config capture.
- Format: the container parser/packer in [tools/](../tools) round-trips the official package byte-for-byte, which is how each format claim here is checked.

## Document map

- [01-hardware-flash-map.md](01-hardware-flash-map.md) — SoC, 2 MB NOR layout, partitioning
- [02-ota-container-format.md](02-ota-container-format.md) — container format and CRC recipe, byte for byte
- [03-firmware-image-layout.md](03-firmware-image-layout.md) — decompressed image structure
- [04-security-model.md](04-security-model.md) — trust boundaries, what is and is not verified
- [05-ble-gatt-and-commands.md](05-ble-gatt-and-commands.md) — GATT map, command protocol, TOTA v2 transport
- [06-ota-protocol.md](06-ota-protocol.md) — OTA command set, send sequence, the TWS-role gate
- [07-app-side-analysis.md](07-app-side-analysis.md) — app OTA-config path, RSA verifier, no pinning
- [08-delivery-method.md](08-delivery-method.md) — reproducible owner-device delivery method
- [09-function-catalog.md](09-function-catalog.md) — IDA function catalogue by module
- [10-factory-console.md](10-factory-console.md) — verified 59-command factory/engineering console

## Scope and limitations

- The ROM / secondary bootloader (flash `0x000000`–`0x010000`) is not part of any
  OTA image and was not dumped. Statements about boot-time verification are
  bounded by (a) the absence of verification primitives in the application image
  and (b) the empirical fact that a modified-but-CRC-valid image booted and ran.
- Version readback over BLE (DeviceInfo feature `12`) returned `2.0.0` both before
  and after a confirmed official 2.9.0 update on this unit, so it is **not** a
  reliable post-update version oracle. The app's own About screen is the
  user-facing version.
- The factory/engineering console ([10](10-factory-console.md)) exists and can
  write device identity and calibration, but its over-the-air reachability was
  not demonstrated — the dispatch table has no direct cross-reference, and only a
  UART entry path is established. Treated as an open question, not a remote surface.
- Findings are from one hardware unit and the firmware revisions named above.
