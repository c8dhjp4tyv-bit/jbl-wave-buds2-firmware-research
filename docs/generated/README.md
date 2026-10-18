# Generated analysis catalogs

These files are derived metadata — addresses, sizes, hashes, offsets, and names.
They contain **no firmware bytes**. Each file is reproducible from an input you
supply yourself (see the regenerate column), and is anchored to one of two
builds (see [two-build provenance](../PROVENANCE.md)):

- **2.9.0 package** — the distribution artifact this repository ships tooling for
  (build `Sep 18 2026`, rev `d5567b8-dirty`). Container, CRC, and factory-table
  data come from its decompressed image.
- **analyzed build** — `wavebuds.elf` (build `Apr 22 2025`, rev `d30e8f1`), the
  image loaded in IDA. All reverse-engineered function/RAM/string addresses come
  from it. The 2.9.0 build is recompiled and relocates these addresses.

| File | Rows | Build | Meaning | Regenerate |
|---|---:|---|---|---|
| `package_inventory.json` | 1 | 2.9.0 | package size, MD5/SHA-256, decompressed SHA-256, stream count, CRC | `inventory_ota_container.py` |
| `ota_container_layout.csv` | 8 | 2.9.0 | per-LZMA-stream file offset, compressed/decompressed size, image offset | `inventory_ota_container.py` |
| `factory_command_table.csv` | 54 | 2.9.0 | factory/engineering command entries located structurally (command, handler VA, name VA) | `extract_factory_table.py` |
| `crc_test_vectors.csv` | 2 | 2.9.0 | CRC-32 recipe test vectors | `crc_check.py` |
| `cross_build_map.csv` | 20 | both | one-to-one address map between the analyzed and 2.9.0 builds | two IDA analyses (see command log) |
| `analyzed_functions.csv` | 15 | analyzed | reverse-engineered functions with role, evidence class, confidence | manual (IDA; see command log) |
| `ram_state_vars.csv` | 12 | analyzed | OTA RAM state variables and the handler case that sets each | manual (IDA) |
| `string_anchors.csv` | 13 | analyzed | key string/table anchors with VAs | manual (IDA) |

## Full function inventory

The complete per-function enumeration (7,960 functions, 250 named, 7,710
auto-named `sub_*`) is **not** kept inline — it is mostly stripped auto-analysis
starts with no recovered semantics, and would be noise. It is reproducible with
[`../../tools/export_ida_inventory.py`](../../tools/export_ida_inventory.py),
which writes `function_inventory.csv`, `string_inventory.csv`, and `segments.csv`
from an open IDA database of the analyzed build. The curated, semantically
recovered subset is `analyzed_functions.csv`.

## Conventions

- Evidence classes follow [PROVENANCE.md](../PROVENANCE.md): `STATIC_IDA`,
  `STATIC_RAW`, `HARDWARE`, `UNRESOLVED`.
- `UNRESOLVED` is a classification, not a blank: it marks a field whose evidence
  is not available (e.g. a function size not confirmed by decompilation), rather
  than substituting a guess.
- `factory_command_table.csv` is located structurally (longest run of valid
  `[handler][name_ptr]` entries), so its count is an analysis observation of the
  2.9.0 build. The analyzed build exposes 59 entries at shifted addresses; this
  cross-build difference is itself a finding (see PROVENANCE.md).
