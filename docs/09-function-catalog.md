# 09 — Function catalogue

Addresses are at image base `0x2C010000`. Auto-analysis found 7960 functions, most
unnamed; the entries below are the ones identified from trace-tag strings,
cross-references, and the OTA/flash/transport work in this repository. They can be
re-derived by opening the decompressed image in IDA and following the cross-references.

## OTA / flash

| Address | Role |
|---|---|
| `sub_2C0CD0BC` | `ota_init_flash` — `norflash_api` register, 0x2000-byte block |
| `sub_2C091384` | `ota_register_user` — registers a flash region in the OTA user table (RAM ~`0x20027400`) |
| `sub_2C092014` | aligned flash copy, destination base `0x28120000` (offset `0x120000`); no verification |
| `sub_2C0DB3E0` / `sub_2C0DAD80` / `sub_2C0DB350` | sector erase / program / flush |

## OTA command handling and the state gate

| Address | Role |
|---|---|
| `sub_2C0918BC` (0x622) | main OTA command handler; opcode dispatch (`0x80` start / `0x86` config / `0x82` segment-CRC / `0x85` data / `0x92` overwrite); every integrity check is CRC-32 |
| `sub_2C091488`, `sub_2C0911B4`, `sub_2C091EE0`, `sub_2C091300`, `sub_2C0909A8` | OTA handler helpers |
| `sub_2C0905E4` | OTA-state gate: returns true only when `MEMORY[0x20026BA0]` ∈ {2, 4} (18 call sites across the cluster) |
| `app_tota_cmd_handler` (~`sub_2C09236C` / `sub_2C092494`) | TOTA command handler + response supervision |
| `sub_2C0CE944` | CRC-32 (table-driven; table at `0x2C0F5218`) — config / segment / whole-image integrity |

## SPP / command transport

| Address | Role |
|---|---|
| `sub_2C0941CC` | SPP RX reassembly (17-byte `BE 05` control packet resets the buffer); dispatches a full packet to `sub_2C0937F0` |
| `sub_2C0937F0` / `sub_2C093790` | next dispatch layer |

## Factory / engineering console

| Address | Role |
|---|---|
| `0x2C0F10B0` | command table, 59 entries (`[handler][name_ptr]`) |
| `sub_2C067E0C` | `UARTCMD` handler (response `,1,%s\n`); UART `communication_server` thread |

The full 59-entry factory command table (MAC/BLE-address write, crystal trim,
ANC engineering, download/DUT/ship modes, link-key access, etc.) is cataloged
separately; those commands read or write device identity and radio calibration
and are listed for completeness, not as a recommended thing to exercise.

## Logging / runtime

| Address | Role |
|---|---|
| `sub_2C0DB460` | printf/log (`TAG, fmt`) — most cross-referenced function (501+) |
| `sub_2C0DB100` / `sub_2C0DB180` | memcpy / sprintf-like |
| `hal_trace_crash_dump_register`, `OS_Assert` | debug / crash infrastructure |

## Notable constants

| Address | Content |
|---|---|
| `0x2C010000` | image header (`ff ff ff ff 00 00 04 00 00 00 00 00` + ptr `0x2C0F899C`) |
| `0x2C01FA60` | `RTX V5.5.1` |
| `0x2C03487B` / `0x2C03E168` | `HARMAN+JBL_WAVE_BUDS2+20240516+V1.0.4` |
| `0x2C0F899C` | embedded build-config blob |
| `0x2C0162B3` | ` (SecureFault)` — Cortex-M33 exception name |
| `0x2C0F5218` | CRC-32 lookup table |
| `0x2C0F10B0` | factory command table, 59 entries; see [10](10-factory-console.md) |
