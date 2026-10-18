# IDA analysis command log

A reproducible record of the IDA (Hex-Rays) queries behind the function-level
findings. All run against the analyzed build `wavebuds.elf` (input SHA-256
`b74c291f2e4b323a5c0fe1cc786afd236a721cbc620a8320e5ac99191dbfb13e`), image base
`0x2C010000`. Tooling was IDA 9.4 driven over an MCP bridge; every step below is a
plain IDA action (open, survey, decompile, xrefs, read bytes, string search).

## Setup

- Open `wavebuds.elf` and run auto-analysis + Hex-Rays.
- `survey_binary` → one `.text` segment `0x2C010000`–`0x2C0F8B44` (`0xE8B44` =
  953,156 bytes), **7,960 functions** (250 named, 7,710 `sub_*`), 1,332 strings,
  entry `0x2C01000C`.

## Absence of signing (docs/04)

- String search `(?i)(secure|sec_?boot|signatur|verify|rsa|ecdsa|sha-?256|authenticat|rollback)`
  → single hit `" (SecureFault)"` at `0x2C0162B3` (Cortex-M33 exception name).
- String search `(?i)(crc|md5|sha1|sha256|hmac|crypt|cipher)` → `OTA_SEGMENT_CRC`,
  `CRC32_OF_IMAGE=0x`, `ENCRYPTION_CHANGE`, `em_bt_txrxcntl_txcrypt_setf`, and the
  build-config blob. No image signature/hash primitive.

## Flash + OTA primitives (docs/01, docs/06)

- `decompile 0x2C092014` → aligned flash copy to base `0x28120000`; erase/program
  only, no verification.
- `decompile 0x2C091384` → `ota_register_user` (flash region table ~`0x20027400`).
- String search `(?i)(ota|upgrade|reboot|boot_|flash_program)` → OTA command log
  tags (`OTA_GET_VERSION`/`OTA_START`/`OTA_CONFIG`/`OTA_SEGMENT_CRC`), build-config
  blob at `0x2C0F899C`.

## OTA command handler + integrity (docs/04, docs/06)

- `decompile 0x2C0918BC` → opcode dispatch: `0x80` startOTA (size → `0x2002739C`,
  CRC → `0x200273AC`, `"BEST"`), `0x86` OTAConfigure (len 92, CRC-32 over first 88
  bytes, `MEMORY[0x20027418]`), `0x82` segmentCRC (running CRC `0x200273B0`), `0x85`
  dataPacket (staging), `0x92` imageOverwriteConfirm (activation flag
  `0x200274F4`). Diagnostic string `"plaese check config len. %d != %d"`.
- `decompile 0x2C0CE944` → table-driven CRC-32 (`~init`, `table[(b^crc)&0xFF]^(crc>>8)`,
  `~final`; table `0x2C0F5218`). This is the only checksum the handler uses.

## The accept gate (docs/06)

- `decompile 0x2C0905E4` → `return MEMORY[0x20026BA0] == 2 || == 4;`.
- `xrefs_to 0x2C0905E4` → 18 call sites across the OTA handler cluster
  (`0x2C0918BC`, `0x2C091488`, `0x2C0911B4`, `0x2C091EE0`, `0x2C091300`,
  `0x2C0909A8`, …).

## Factory console (docs/10)

- `get_bytes 0x2C0F10B0` (480 bytes) → 59 `[handler][name_ptr]` entries.
- `get_bytes 0x2C0DC800` (name blob) → command names (`_NTC`,`CIDW`,`CIDR`,…,
  `SETMACADDR`,`SETTRIM`,`LINKKEY`,`HMLICENSE`,…,`AT+TEST=`).
- `xrefs_to 0x2C0F10B0` and `xrefs_to 0x2C067E0C` → **none** (computed dispatch);
  over-the-air reachability left `UNRESOLVED`.

## Image identity + constants (docs/03)

- `get_bytes 0x2C010000` (16) → header `ff ff ff ff 00 00 04 00 00 00 00 00` + ptr
  `0x2C0F899C`.
- String search `HARMAN\+JBL_WAVE_BUDS2` → `0x2C03487B` (and `0x2C03E168`);
  `RTX V5` → `0x2C01FA60`.

## Cross-build differential (docs/PROVENANCE)

- `get_bytes` at `0x2C0918BC`, `0x2C0905E4`, `0x2C0CE944` on the analyzed build,
  compared byte-for-byte against the 2.9.0 decompressed image at the mapped
  offsets → **all differ**: the functions are relocated/recompiled between builds.
- The 2.9.0 factory table (located structurally by `tools/extract_factory_table.py`)
  holds 54 contiguous entries at `0x2C0F1A18` with `CIDR` handler `0x2C068F01`,
  versus 59 entries at `0x2C0F10B0` with `CIDR` handler `0x2C068EED` in the
  analyzed build.

## Enumeration note

The MCP listing calls (`list_funcs`, `func_profile`) cap output at a few rows, so
the full 7,960-function table is not exported here. Regenerate it with
`tools/export_ida_inventory.py` inside IDA; the curated subset is
`docs/generated/analyzed_functions.csv`.
