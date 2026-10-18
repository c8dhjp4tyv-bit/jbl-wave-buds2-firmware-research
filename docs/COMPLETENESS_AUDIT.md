# Completeness audit

"Complete" here means every item is either evidenced or explicitly marked
`UNRESOLVED`. It does not mean every function was understood or that missing
evidence was invented.

## Quantitative summary

| Quantity | Value | Source |
|---|---:|---|
| Package size (2.9.0) | 549,558 bytes | `package_inventory.json` |
| Decompressed image (2.9.0) | 955,596 bytes | `package_inventory.json` |
| LZMA streams | 8 | `ota_container_layout.csv` |
| Container CRC-32 | `A0C7CCEC` (valid) | `crc_test_vectors.csv` |
| Analyzed image `.text` | 953,156 bytes (`0x2C010000`–`0x2C0F8B44`) | IDA survey |
| Functions (analyzed build) | 7,960 (250 named, 7,710 `sub_*`) | IDA survey |
| Strings (analyzed build) | 1,332 | IDA survey |
| Reverse-engineered functions | 15 | `analyzed_functions.csv` |
| OTA RAM state variables | 12 | `ram_state_vars.csv` |
| String/table anchors | 13 | `string_anchors.csv` |
| Factory commands | 54 (2.9.0) / 59 (analyzed) | `factory_command_table.csv` |

## Audit table

| Requirement | Artifact / result | Status |
|---|---|---|
| OTA container format fully specified | `docs/02`, `ota_container_layout.csv`; byte-identical repack of the official package | **Complete**; verified by round-trip in `ota_repack.py` |
| CRC recipe verified | `docs/02`, `crc_test_vectors.csv`, `crc_check.py --selftest` + the 2.9.0 vector | **Complete** |
| OTA command set and integrity model | `docs/06`, handler `0x2C0918BC` decompiled | **Complete** for opcodes and CRC checks; runtime timing/role transitions `UNRESOLVED` |
| No on-device firmware signing | `docs/04`; exhaustive string/routine search; handler decompile; empirical boot of a modified image | **Complete** as static + hardware evidence; the ROM bootloader (`0x000000`–`0x010000`) is outside every OTA image and bounds the claim |
| Function enumeration | IDA survey (7,960); `export_ida_inventory.py` | **Complete** as enumeration; semantics recovered only for the OTA/flash/factory/CRC cluster (`analyzed_functions.csv`); the remainder is `UNRESOLVED` |
| Factory/engineering console inventory | `factory_command_table.csv`, `docs/10` | **Complete** as a name/handler inventory; **over-the-air reachability `UNRESOLVED`** |
| OTA RAM state variables | `ram_state_vars.csv` | **Partial**; OTA-path variables evidenced from the handler; the broader RAM map is `UNRESOLVED` |
| Flash / partition map | `docs/01` from the embedded build-config blob | **Complete** for partition boundaries; the exact staging-region top is inferred from the copy base |
| Cross-build provenance + re-anchoring | `PROVENANCE.md`, `ADDRESS_LEDGER.md`, `cross_build_map.csv` | **Complete**; the 2.9.0 image was analyzed directly (ELF wrap, 8,126 functions) and the OTA handler/gate/CRC re-anchored — they decompile identically to the analyzed build |
| Second-tool cross-check | — | `UNRESOLVED`; Ghidra was not run for this release |
| Dynamic validation | `HARDWARE` observations (official + one-byte-modified flash both succeeded) | **Partial**; owner-observed on a single unit; no UART/SWD capture |
| AI / evidence provenance | `PROVENANCE.md` | **Complete** |

## Coverage boundary

Semantic recovery is **deep** for the OTA, flash, CRC, delivery, and factory-table
subsystems and **shallow (enumeration only)** for audio/ANC, codec, and the
Bluetooth stack. The analyzed `.text` (953,156 bytes) and the 2.9.0 decompressed image
(955,596 bytes) are different kinds of ranges from separately compiled builds;
the size difference is not evidence of a missing disassembly range (see
[PROVENANCE.md](PROVENANCE.md)).

## External blockers

The `UNRESOLVED` items cannot be closed from the firmware package alone. They
need a ROM/bootloader dump, UART/SWD capture, and an independent second-tool
cross-check. Direct IDA analysis of the 2.9.0 image has already been performed. Until then,
the repository does not claim "every function understood" or "secure boot proven
absent in the ROM."
