# Testing and reproducibility

## Correctness anchor

The format claims rest on a round-trip guarantee: `ota_repack.py` recompresses
the official package and refuses to emit anything unless an unchanged repack is
**byte-identical** to the source. A format-handling error is less likely to
silently produce a corrupt image; this round-trip property does not prove that
an arbitrary modified image is safe to flash. The CRC recipe is independently checked by
`crc_check.py` against both the 2.9.0 container value (`A0C7CCEC`) and a
synthetic self-test vector.

## Test suite

`tests/` runs under `unittest` (and `pytest`), in both normal and optimized
(`python -O`) modes, matching CI:

| Test | Checks |
|---|---|
| `test_ota_container.py` | synthetic round-trip, malformed magic/length/trailer/CRC and oversized-block rejection; optional real-package check (skipped when not supplied) |
| `test_crc_recipe.py` | the documented CRC-32 recipe and `--selftest` vector |
| `test_safety_guards.py` | invalid source, bad CRC, and out-of-range decompressed-byte offset fail **under `python -O`** (guards are real checks, not `assert`) |
| `test_factory_table.py` | the structural locator finds a plausible command table in a synthetic image and resolves names |
| `test_generated_completeness.py` | every shipped `docs/generated/*.csv` has its header and non-empty rows, and `package_inventory.json` has the required keys |

Safety guards in the production tools never use `assert`, so they stay active
under `python -O`; CI runs both modes. Public CI uses synthetic fixtures and
**does not validate the owner-held official 2.9.0 package** unless provided
explicitly via `WAVEBUDS_PACKAGE`.

## Reproducing the generated data

All generated data is derived from inputs you supply (no firmware is shipped):

```bash
# 1. decompress your own official package
python3 tools/ota_unpack.py <official_2.9.0_package.bin> --extract image.bin

# 2. container metadata (2.9.0 build)
python3 tools/inventory_ota_container.py <official_2.9.0_package.bin> \
    --csv docs/generated/ota_container_layout.csv \
    --json docs/generated/package_inventory.json

# 3. factory command table (structurally located, build-independent)
python3 tools/extract_factory_table.py image.bin \
    -o docs/generated/factory_command_table.csv

# 4. CRC vectors
python3 tools/crc_check.py <official_2.9.0_package.bin>
python3 tools/crc_check.py --selftest
```

The function-level catalogs (`analyzed_functions.csv`, `ram_state_vars.csv`,
`string_anchors.csv`) are from the analyzed build (`wavebuds.elf`) in IDA; the
full per-function inventory regenerates with `tools/export_ida_inventory.py` run
inside IDA (see [analysis/IDA_MCP_COMMAND_LOG.md](../analysis/IDA_MCP_COMMAND_LOG.md)).

## Continuous integration

`.github/workflows/tests.yml` runs the suite on every push and pull request,
under both normal and `-O` Python, on a pinned Python 3.12.
