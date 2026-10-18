# Analysis and evidence provenance

## Authorship boundary

The analysis scripts, generated catalogs, documentation, and static
interpretations in this repository were produced by an AI assistant (Claude).
The owner supplied the firmware, operated the phone and earbuds, and performed
the hardware flashes. No claim here has had an independent human
reverse-engineering review. Narrative claims carry addresses, disassembly, or a
link to generated evidence so they can be checked.

## Two-build provenance

Two distinct firmware builds are used, and every address is attributed to one of
them. They are the same product and share early code, but they are **separately
compiled**: functions are relocated and their bytes differ.

| Role | Build | Identity |
|---|---|---|
| Distribution package (flashing target; container/CRC/factory data) | **2.9.0** | `COMPRESS_WAVE_BUDS2_OTA2_V2.9.0_56e441_20260918.bin`; packaged SHA-256 `836cb251f9fb2261dde14f39ba18d358c48018817f3c3d1b527e1ac5f3ab7ba2`; decompressed SHA-256 `489663e80b76f20f4c94671064908569fac5f4e3df10ab6d7369baffe094f67d`; `BUILD_DATE=Sep 18 2026 10:43:07`, `REV_INFO=d5567b8-dirty` |
| Analyzed image (all function/RAM/string VAs) | **`wavebuds.elf`** | input SHA-256 `b74c291f2e4b323a5c0fe1cc786afd236a721cbc620a8320e5ac99191dbfb13e`; mapped `.text` `0x2C010000`–`0x2C0F8B44`; `BUILD_DATE=Apr 22 2025 15:36:42`, `REV_INFO=d30e8f1` |

Neither image is redistributed. The package is obtained from JBL's OTA server;
the analyzed image is an owner-held dump of an earlier build.

## Differential (verified)

- **Shared early code.** The `RTX V5.5.1` string is at decompressed offset
  `0xFA60` in both builds; the static product id
  `HARMAN+JBL_WAVE_BUDS2+20240516+V1.0.4` is at `0x2487B` in both.
- **Relocated/recompiled later code.** At the analyzed-build VAs, the 2.9.0 image
  holds different bytes: the OTA handler (`0x2C0918BC`), the OTA-state gate
  (`0x2C0905E4`), and the CRC-32 routine (`0x2C0CE944`) all differ, so these
  functions moved between builds.
- **Factory table.** Analyzed build: 59 entries at `0x2C0F10B0` (e.g. `CIDR`
  handler `0x2C068EED`). 2.9.0 build: 54 contiguous entries at `0x2C0F1A18`
  (`CIDR` handler `0x2C068F01`). Command names are stable; addresses and counts
  are not.
- **Three version namespaces.** The OTA release label (`2.9.0`), the build
  date/revision (differs per build), and the static product id (`V1.0.4`,
  constant) are independent. This is why the BLE `DeviceInfo` version readback
  does not track the OTA release (see
  [03-firmware-image-layout.md](03-firmware-image-layout.md)).

The architectural findings — CRC-32-only image integrity, the staged OTA, the
TWS-state accept gate, the factory console, no on-device signing — hold for both
builds. Exact addresses are build-specific and ledgered in
[ADDRESS_LEDGER.md](ADDRESS_LEDGER.md).

## Evidence classes

| Label | Meaning |
|---|---|
| `STATIC_IDA` | IDA disassembly / decompilation / xref evidence on the analyzed build |
| `STATIC_RAW` | independent byte/format parser in `tools/` (container, CRC, factory table), run on the 2.9.0 package |
| `HARDWARE` | owner-observed behavior on the author's unit |
| `UNRESOLVED` | required evidence is absent; no guess is substituted |

## Hardware-confirmed observations

- The unchanged official 2.9.0 image, delivered through the patched app + a
  user-CA MITM, completed with "Update Successful".
- A 2.9.0 image modified in exactly one decompressed byte (`RTX V5.5.1` →
  `V5.5.2` at offset 64096, container CRC recomputed) was delivered the same way;
  the app reported "Update Successful", the device rebooted, and it remained
  fully functional (A2DP audio, app connectivity, About showed `v2.9.0`).
- The read-only BLE `DeviceInfo` version returned `2.0.0` both before and after a
  confirmed official 2.9.0 update, so it is not a reliable post-update oracle.

These are owner observations on a single unit, not independent laboratory
reproduction.

## Evidence still required

- UART / SWD access to the BES1306 and a dump of the ROM / secondary bootloader
  (`0x000000`–`0x010000`), the one region outside every OTA image.
- Whether the factory/engineering console is reachable over the wireless command
  channel (see [10-factory-console.md](10-factory-console.md)).
- A second-tool (e.g. Ghidra) cross-check of function starts on the analyzed
  build.
- Re-anchoring the OTA function addresses onto the 2.9.0 build by analyzing its
  decompressed image directly.

Until supplied, the affected fields remain `UNRESOLVED`.
