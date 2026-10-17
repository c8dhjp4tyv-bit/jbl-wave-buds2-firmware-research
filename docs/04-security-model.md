# 04 — Security model

This chapter states exactly what the OTA path protects, what it does not, and the
evidence for each claim.

## What protects what

| Boundary | Mechanism | What it actually guarantees |
|---|---|---|
| Device authenticity | RSA-2048 in the app (`com.jbl.counterfeit.Rsa2048DynamicVerifier`), `AuthenticateDevice` feature | The earbuds are a genuine Harman product, to the app. **Not** firmware signing. |
| OTA transport | BES "TOTA v2": AES-128-CBC session, key derived client-side (see [05](05-ble-gatt-and-commands.md)) | Confidentiality/integrity of the BLE link during a session. **Not** authenticity of the image at rest. |
| OTA image integrity | CRC-32 — container trailer (see [02](02-ota-container-format.md)); per-16 KiB segment CRC-32 and a whole-image CRC-32 in the protocol (see [06](06-ota-protocol.md)) | Detects corruption in transit. **Not** tampering. |

## What is not present

- No cryptographic **signature** over the firmware image (no RSA/ECDSA/Ed25519
  verify applied to the image).
- No image **hash** used for authentication (no SHA-1/SHA-256/MD5/HMAC over the image).
- No **anti-rollback** / downgrade enforcement in the application image.

Evidence — an exhaustive string and routine search of the 955,596-byte
application image (IDA, 7960 functions):

- The only integrity/crypto matches are `OTA_SEGMENT_CRC`, `CRC32_OF_IMAGE=0x`
  (the two CRC mechanisms), `ENCRYPTION_CHANGE` and the link-layer
  `em_bt_txrxcntl_txcrypt_setf` (Bluetooth transport, not the image), and the
  Cortex-M33 `SecureFault` exception name at `0x2C0162B3` (an ARM fault handler,
  unrelated to OTA).
- There are **zero** occurrences of `sign`, `signature`, `rsa`/`ecdsa`,
  `sha1`/`sha256`, `hmac`, `verify image`, or `secure boot` applied to the image.
- The flash-copy routine `sub_2C092014` erases and programs bytes with no hash,
  CRC, or signature check of its own.

## Secure boot

BES1306 is a Cortex-M33 with TrustZone-M (the `SecureFault` handler confirms the
silicon capability), so hardware secure boot is *possible* in principle. The ROM
/ secondary bootloader at flash `0x000000`–`0x010000` is outside every OTA image
and was not dumped, so it cannot be inspected directly. Two independent
observations bound the question:

1. The OTA image format carries **no signature block** — parsed byte-for-byte in
   [02](02-ota-container-format.md), it is only LZMA streams plus a CRC-32
   trailer. There is nowhere for a signature to live.
2. A CRC-valid image with a **single modified byte** (an application `.rodata`
   string, offset 64096; see [03](03-firmware-image-layout.md)) was delivered
   through the app's own OTA path. The device reported the update successful,
   rebooted, and remained fully functional — A2DP audio, app connectivity, and
   the About screen all normal.

If secure boot were enforced over the application region on this unit, (2) could
not occur. Conclusion: **on this retail unit there is no effective
signature or secure-boot check on the application image; integrity rests on
CRC-32 alone.**

## Brick surface

- **Download phase — safe.** The new image is staged at `0x120000` while the
  running application at `0x010000` is untouched (see [01](01-hardware-flash-map.md)).
- **Activation phase — the risk window.** The post-reboot staging→application
  copy will move a CRC-valid-but-broken image into place and run it. No rollback
  or fallback path was identified in the application image, and no exposed
  hardware recovery (e.g. a USB DFU pin) was surfaced. The hazard of firmware
  modification is therefore **not** signature rejection but a functionally bad
  image that still passes CRC.

## Where the real gate is

Because the firmware-signing boundary that would normally prevent loading a
modified image is absent, the only gate left is **app-side**: the companion app
verifies the OTA *configuration* with RSA-2048 and will only download and flash
what that configuration authorizes (see [07](07-app-side-analysis.md)). That gate
runs on the phone, inside the app's trust store — which is the entire basis of
the delivery method documented in [08](08-delivery-method.md). This is the
disclosure-relevant finding: image trust is delegated to a client-side config
check with no on-device signature backstop.
