# Address ledger

Every address in this repository belongs to one build. Mixing them is a mistake,
because the two builds are separately compiled and relocate code (see
[PROVENANCE.md](PROVENANCE.md)). This ledger is the single place that states
which build each address set comes from.

## Analyzed build (`wavebuds.elf`, Apr 22 2025, rev d30e8f1)

Source of all function, RAM, and string addresses in docs 03–10 and in
`generated/analyzed_functions.csv`, `generated/ram_state_vars.csv`,
`generated/string_anchors.csv`. Image base `0x2C010000`.

| Address | Meaning |
|---|---|
| `0x2C01000C` | image entry stub |
| `0x2C01FA60` | `RTX V5.5.1` |
| `0x2C03487B` / `0x2C03E168` | `HARMAN+JBL_WAVE_BUDS2+20240516+V1.0.4` |
| `0x2C0905E4` | OTA-state gate (`MEMORY[0x20026BA0] ∈ {2,4}`) |
| `0x2C0918BC` | OTA command handler (opcode dispatch) |
| `0x2C091384` | `ota_register_user` |
| `0x2C092014` | aligned flash copy (dest base `0x28120000`) |
| `0x2C0CD0BC` | `ota_init_flash` |
| `0x2C0CE944` | CRC-32 routine (table `0x2C0F5218`) |
| `0x2C0DB3E0` / `0x2C0DAD80` / `0x2C0DB350` | flash erase / program / flush |
| `0x2C0DB460` | log printf |
| `0x2C0941CC` / `0x2C0937F0` | SPP RX reassembly / dispatch |
| `0x2C067E0C` | `UARTCMD` handler |
| `0x2C0F10B0` | factory command table (59 entries) |
| `0x2C0F5218` | CRC-32 lookup table |
| `0x2C0F899C` | build-config blob |
| `0x20026BA0` | OTA accept-state variable |
| `0x200274F4` | OTA activation flag |
| `0x2002739C` / `0x200273AC` / `0x200273B0` | OTA image size / expected CRC / running CRC |
| `0x20027418` | OTA config CRC |

## 2.9.0 build (Sep 18 2026, rev d5567b8-dirty)

Source of the container/CRC/factory-table generated data and the flashing
procedure. Decompressed image base `0x2C010000`; package layout in
`generated/package_inventory.json` and `generated/ota_container_layout.csv`.

| Item | Value |
|---|---|
| OTA command handler | `0x2C0918EC` (size 0x622; identical decompile to the analyzed build) |
| OTA-state gate | `0x2C0905FC` (`MEMORY[0x20026BC8] ∈ {2,4}`) |
| CRC-32 function / table | `0x2C0CF480` / `0x2C0F5BC0` |
| OTA RAM vars | image size `0x200273C4`, expected CRC `0x200273D4`, running CRC `0x200273D8`, config CRC `0x20027440`, activation flag `0x2002751C` (analyzed values `+0x28`) |
| Factory table | `0x2C0F1A18` (offset `0xE1A18`), 54 contiguous entries; `CIDR` handler `0x2C068F01` |
| `communication_server` thread entry | `0x2C094750` (UART engineering task) |
| Build config / RTX / HARMAN id | `0x2C0F931C` / `0x2C01FA60` / `0x2C03487B` |
| Container trailer | file offset `0x8629C`, `CRC32_OF_IMAGE=0xA0C7CCEC`, CRC input `[0x0, 0x862AD)` |

The 2.9.0 image was analyzed directly in IDA (an ARM ELF wrap of the decompressed
image; 8,126 functions). The OTA handler, gate, and CRC routine were located by
string xref and **decompile identically** to the analyzed build — the subsystem
is build-invariant. The full one-to-one correspondence is in
[`generated/cross_build_map.csv`](generated/cross_build_map.csv); current factory
entries are in `generated/factory_command_table.csv`.

## Rule

Each build's addresses are listed above and mapped one-to-one in
[`generated/cross_build_map.csv`](generated/cross_build_map.csv). A function VA
from one build does not land on the same function in the other — use the column
for the build you are reproducing against. The code shift is per-function
(recompilation); the OTA RAM region shifted by a uniform `+0x28`.
