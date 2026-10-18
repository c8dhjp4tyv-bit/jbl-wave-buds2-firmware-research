# 04 — Security model

This chapter states exactly what the OTA path protects, what it does not, and the
evidence for each claim.

## What protects what

| Boundary | Mechanism | What it actually guarantees |
|---|---|---|
| Device authenticity | RSA-2048 in the app (`com.jbl.counterfeit.Rsa2048DynamicVerifier`), `AuthenticateDevice` feature | The earbuds are a genuine Harman product, to the app. **Not** firmware signing. |
| OTA transport | BES "TOTA v2": AES-128-CBC session, key derived client-side (see [05](05-ble-gatt-and-commands.md)) | Encrypted BLE session payloads. AES-CBC and CRC do **not** alone provide cryptographic message integrity or authenticate the image. |
| OTA image integrity | CRC-32 — container trailer (see [02](02-ota-container-format.md)); per-16 KiB segment CRC-32 and a whole-image CRC-32 in the protocol (see [06](06-ota-protocol.md)) | Detects corruption in transit. **Not** tampering. |

## What was not identified in the inspected application OTA path

- No cryptographic **signature verification** over the firmware image (no
  RSA/ECDSA/Ed25519 verify applied to the image in the inspected path).
- No image **hash** used for authentication in that path (no
  SHA-1/SHA-256/MD5/HMAC over the image).
- No **anti-rollback** / downgrade enforcement was identified in the application image; bootloader behavior remains unexamined.

The original string/routine searches and addresses below belong to the analyzed
`wavebuds.elf` build (7,960 functions; mapped `.text` size 953,156 bytes).
The separate 2.9.0 image decompresses to 955,596 bytes and yielded 8,126 functions
in its direct IDA analysis. Its key OTA functions were re-anchored as described
below and in [PROVENANCE.md](PROVENANCE.md).

- The reported search anchors are `OTA_SEGMENT_CRC`, `CRC32_OF_IMAGE=0x`
  (the two CRC mechanisms), `ENCRYPTION_CHANGE` and the link-layer
  `em_bt_txrxcntl_txcrypt_setf` (Bluetooth transport, not the image), and the
  Cortex-M33 `SecureFault` exception name at `0x2C0162B3` (an ARM fault handler,
  unrelated to OTA).
- Those searches did not identify image verification using `sign`, `signature`,
  `rsa`/`ecdsa`, `sha1`/`sha256`, `hmac`, `verify image`, or `secure boot`.
  Missing strings alone do not establish that cryptographic code is absent.
- The flash-copy routine `sub_2C092014` erases and programs bytes with no hash,
  CRC, or signature check of its own.

## Device-side confirmation (the OTA handler)

The claim above is not only from the absence of strings. The OTA command handler
`sub_2C0918BC` was decompiled, and every integrity check it performs is CRC-32:

- The integrity primitive is `sub_2C0CE944`, a textbook table-driven CRC-32
  (`~init`; `table[(byte ^ crc) & 0xFF] ^ (crc >> 8)`; `~final`; table at
  `0x2C0F5218`). It is the only checksum the handler uses.
- `OTAConfigure` (opcode `0x86`) rejects a wrong config length ("plaese check
  config len. %d != %d", expecting 92 bytes) and validates the config's own
  CRC-32 over its first 88 bytes (`MEMORY[0x20027418] == sub_2C0CE944(0, cfg, 88)`).
- `segmentCRC` (opcode `0x82`) compares a running CRC-32 of the received data to
  the value carried after the `"BEST"` magic (`0x54534542`).
- `startOTA` (opcode `0x80`) records the image size and expected CRC-32 and
  enforces the `"BEST"` magic.
- `imageOverwriteConfirm` (opcode `0x92`) sets the activation flag
  (`MEMORY[0x200274F4] = 1`) only once the whole-image CRC matches.

No signature or hash verification appears anywhere in the handler — only CRC-32
and a magic constant. This establishes the CRC-only checks in the inspected
application handler; it does not establish the behavior of the ROM bootloader.

The same handler, gate, and CRC routine were re-confirmed by a direct IDA
analysis of the **2.9.0** build (`sub_2C0918EC` / `sub_2C0905FC` / `sub_2C0CF480`),
where the same checks were recovered. This finding covers these two inspected
builds; see
[PROVENANCE.md](PROVENANCE.md) and [`generated/cross_build_map.csv`](generated/cross_build_map.csv).

## Secure boot

BES1306 is a Cortex-M33 with TrustZone-M (the `SecureFault` handler confirms the
silicon capability), so hardware secure boot is *possible* in principle. The ROM
/ secondary bootloader at flash `0x000000`–`0x010000` is outside every OTA image
and was not dumped, so it cannot be inspected directly. Two independent
observations bound the question:

1. The outer OTA container carries **no separate signature block** — parsed
   byte-for-byte in [02](02-ota-container-format.md), it is LZMA streams plus a
   CRC-32 trailer. This format observation alone does not rule out signed regions
   inside the decompressed image or verification by code outside the OTA image.
2. A CRC-valid image with a **single modified byte** (the final digit of the
   application `.rodata` string beginning at offset 64096; changed at 64105 / `0xFA69`,
   see [03](03-firmware-image-layout.md)) was delivered
   through the app's own OTA path. The device reported the update successful,
   rebooted, and remained fully functional — A2DP audio, app connectivity, and
   the About screen all normal.

The one-byte change was reported to install and the device remained functional.
However, the updated string was **not independently read back from device flash**
or observed at runtime. These observations do not identify the active application
bytes. ROM/bootloader code has not been dumped, so its authentication checks
remain `UNRESOLVED`.

## Activation and recovery limits

- **Download phase — staged.** The new image is staged at `0x120000` while the
  running application at `0x010000` is untouched (see [01](01-hardware-flash-map.md)).
  This reduces transfer-phase risk; it is not a universal recovery guarantee.
- **Activation phase — the risk window.** A CRC-valid-but-broken image can pass
  the inspected application OTA checks and reach the post-reboot copy. No rollback
  or fallback path was identified in the application image, and no exposed
  hardware recovery (e.g. a USB DFU pin) was surfaced. The hazard of firmware
  modification includes a functionally bad image that still passes CRC.
  ROM/bootloader checks and execution of the modified byte remain unverified.

## Where the observed trust boundary sits

The tested product's OTA configuration carried no signature field. The decoded
app includes an RSA-2048 anti-counterfeit verifier, but there is **no evidence**
that this verifier authenticates the PID 2100 OTA configuration. The tested
delivery method changes the owner's app network trust configuration so that a
local proxy can supply a modified configuration and firmware image; it does not
modify device-authenticity logic. The device-side OTA handler verifies CRC-32,
not a firmware-publisher signature. See [07](07-app-side-analysis.md) and
[08](08-delivery-method.md). This result is limited to the tested unit and builds.
