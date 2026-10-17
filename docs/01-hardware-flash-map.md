# 01 — Hardware and flash map

## SoC and address windows

The BES1306 executes from a memory-mapped 2 MB (`0x200000`) NOR flash. Two alias
windows are used throughout the firmware:

- `0x2C000000` — cached (XIP) window. IDA's image base is `0x2C010000`.
- `0x28000000` — non-cached window (`FLASH_NC_BASE`). OTA flash routines address
  staging through this alias (e.g. `0x28120000`).

A third alias, `0x0C000000`, appears in some code pointers (same physical flash).

The device is a Cortex-M33-class ARMv8-M part: the exception table contains a
`SecureFault` handler (`0x2C0162B3`), confirming TrustZone-M is present in
silicon. Whether secure boot is *provisioned* is a separate question — see 04.

## Build configuration (primary source)

The build configuration is embedded verbatim in the image as a string at
`0x2C0F899C`, and is the authoritative source for the layout:

```
CHIP=best1306
KERNEL=RTX5
NV_REC_DEV_VER=2
__userdata_start=0x281EC000
USER_SEC_SIZE=0x1000
__aud_start=0x281B8000
AUD_SEC_SIZE=0
__anc_start=0x281EE000
ANC_SEC_SIZE=0x10000
__factory_start=0x281FF000
FACT_SEC_SIZE=0x1000
FLASH_BASE=0x2C000000
FLASH_NC_BASE=0x28000000
FLASH_SIZE=0x200000
OTA_CODE_OFFSET=0x10000
CRC32_OF_IMAGE=0x00000000
BUILD_DATE=Apr 22 2025 15:36:42
REV_INFO=d30e8f1:best1306_ibrt_anc
```

The `CRC32_OF_IMAGE=0x00000000` here is a placeholder; the real value is written
into the container trailer (see [02](02-ota-container-format.md)), not back into
this blob.

## Derived flash map

Offsets are from the flash base. "Source" distinguishes values read directly from
the build config from those inferred from code.

| Offset | End | Size | Region | Source |
|---|---|---|---|---|
| `0x000000` | `0x010000` | 64 KiB | bootloader / sec_boot + vector table | `OTA_CODE_OFFSET=0x10000`; absent from OTA images |
| `0x010000` | `0x120000` | ~1.06 MiB | application code (XIP) | image base `0x2C010000` |
| `0x120000` | ~`0x1B8000` | ~608 KiB | OTA staging (new image lands here) | copy base `0x28120000` in `sub_2C092014` |
| `0x1B8000` | — | 0 | audio prompts (`__aud_start`) | build config (`AUD_SEC_SIZE=0` on this build) |
| `0x1EC000` | `0x1ED000` | 4 KiB | user data (`USER_SEC`) | build config |
| `0x1EE000` | `0x1FE000` | 64 KiB | ANC data (`ANC_SEC`) | build config |
| `0x1FF000` | `0x200000` | 4 KiB | factory section (`FACT_SEC`) | build config |

The key structural fact for OTA: the new image is written to the staging region
(`0x120000`+) while the running application (`0x010000`+) is left intact, so the
download phase cannot brick the device. The risk window is the post-reboot
activation copy (staging → application); see [05](05-ble-gatt-and-commands.md)
and [04](04-security-model.md).

## Flash primitives (IDA)

| Function | Role |
|---|---|
| `sub_2C0CD0BC` | `ota_init_flash` — `norflash_api` register, 0x2000-byte block |
| `sub_2C091384` | `ota_register_user` — registers a flash region in the OTA user table |
| `sub_2C092014` | aligned flash copy; destination base `0x28120000` |
| `sub_2C0DB3E0` / `sub_2C0DAD80` / `sub_2C0DB350` | sector erase / program / flush |

`sub_2C092014` is a plain erase-and-program copy loop; it performs no hashing,
CRC, or signature check on the bytes it moves. The only integrity values in the
whole OTA path are CRC-32 (see 02 and 04).
