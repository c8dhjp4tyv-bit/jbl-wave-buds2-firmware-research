# Tooling and scope

All tools operate on inputs you supply — your own copy of the official package
(from JBL's server) or your own decompressed image. None of them contain or
require redistributed firmware or app code.

## Inventory

| Tool | Purpose | Operates on |
|---|---|---|
| `ota_unpack.py` | parse a package; report header, streams, CRC; optionally extract the decompressed image | 2.9.0 package |
| `ota_repack.py` | inspect / `make-test` / `repack` with byte patches; byte-identical round-trip guard | 2.9.0 package |
| `crc_check.py` | verify the container CRC-32 recipe; `--selftest` vector | 2.9.0 package |
| `inventory_ota_container.py` | emit per-stream layout CSV + package-inventory JSON | 2.9.0 package |
| `extract_factory_table.py` | structurally locate and dump the factory command table | any decompressed image |
| `export_ida_inventory.py` | export full function/string/segment inventory | analyzed build, inside IDA |
| `tota_v2.py` | BES TOTA v2 transport reference (handshake, key schedule, framing, builders) | live BLE (your device) |
| `ble_query.py` | read-only GATT device-info query | live BLE (your device) |
| `mitm_addon.py` | capture / optionally rewrite the OTA config for your own device | your own traffic |
| `patch_app.sh` | build helper for the delivery method (your own APK) | your own APK |

## Reproducibility boundary

This release is **static + format + owner-hardware**. What is reproducible from
the public repository:

- the container/CRC/factory-table metadata, from your own package/image;
- the full function/string inventory, from your own IDA database of the analyzed
  build.

What is **not** independently reproducible from the repository alone, and is
labeled accordingly:

- the reverse-engineered function/RAM semantics depend on the analyzed build
  (`wavebuds.elf`), pinned by hash in [PROVENANCE.md](PROVENANCE.md);
- a second-tool (Ghidra) cross-check of function starts was not run for this
  release (`UNRESOLVED`);
- key OTA handlers were re-anchored using a direct 2.9.0 decompressed-image IDA
  analysis; independent reproduction still requires the owner-supplied image;
- the hardware observations are owner-reported on one unit.

## What the tools do not do

- They do not redistribute JBL firmware, the modified app, or a ready-to-flash
  custom image.
- They do not bypass device authenticity (the anti-counterfeit RSA path is not
  touched).
- They do not fabricate semantics for stripped functions; unknown fields are
  `UNRESOLVED`.
