# 03 — Firmware image layout (decompressed)

The concatenation of the eight LZMA streams ([02](02-ota-container-format.md)) is
the application image — 955,596 bytes for 2.9.0 — mapped at base `0x2C010000`
(the cached-XIP window; see [01](01-hardware-flash-map.md)). The image has no ELF
section table of its own; the boundaries below are read from the content.

The header dump, approximate section boundaries, and build-config address below
belong to the earlier analyzed `wavebuds.elf`, unless explicitly attributed to
2.9.0. Its mapped `.text` range is 953,156 bytes. The RTX marker and first static
product-id offset were checked in both builds; see [PROVENANCE.md](PROVENANCE.md).

## Image header (first 16 bytes)

```
0x2C010000:  ff ff ff ff  00 00 04 00  00 00 00 00  9c 89 0f 2c
             └── magic ──┘ └0x00040000┘ └── zero ──┘ └→ 0x2C0F899C
```

- `[0:4]`  magic `ff ff ff ff`
- `[4:8]`  `0x00040000` (little-endian)
- `[8:12]` zero
- `[12:16]` pointer `0x2C0F899C` → the embedded build-config string (see 01)

Thumb code begins just after the header.

## Section boundaries (approximate)

| Region | Range (mapped) | Notes |
|---|---|---|
| image header | `0x2C010000` .. `0x2C01000C` | see above |
| `.text` | ~`0x2C01000C` .. ~`0x2C0D8000` | ARM Thumb code (~800 KiB) |
| `.rodata` / strings | ~`0x2C0D8000` .. ~`0x2C0F8B44` | string and symbol tables; build config at `0x2C0F899C` |

Boundaries are approximate — they mark the transition from dense code to the
rodata/string region, not entries in a section table.

## Notable constants (verified)

| String | Mapped address | Decompressed offset |
|---|---|---|
| RTX kernel version `RTX V5.5.1` | `0x2C01FA60` | `0xFA60` (64096) |
| HARMAN build id `HARMAN+JBL_WAVE_BUDS2+20240516+V1.0.4` | `0x2C03487B` (also `0x2C03E168`) | `0x2487B` (149627) |
| build-config blob | `0x2C0F899C` | `0xE899C` |

## The version namespaces do not match

The internal HARMAN build id is `…20240516+V1.0.4` — dated and versioned
independently of the OTA **release** label (`2.9.0`). This is the most likely
reason the BLE `DeviceInfo` firmware-version feature (see
[05](05-ble-gatt-and-commands.md)) reported `2.0.0` on this unit both before and
after a confirmed 2.9.0 update: the GATT version triple and the OTA release label
are separate namespaces. The user-facing version is the app's About screen, not
the GATT triple.

This single-byte region (`RTX V5.5.1`, offset 64096) is also the change used to
test image delivery in [04](04-security-model.md): patching the final byte
(`1` → `2`) and recomputing the container CRC yields an image that differs from
the official one in exactly one decompressed byte. The modified marker was not
read back from the device, so update success alone does not prove its execution.
