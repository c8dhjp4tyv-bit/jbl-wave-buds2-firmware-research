# Coverage, confidence, and limitations

## Confidence by claim

| Claim | Confidence | Basis |
|---|---|---|
| OTA container format and CRC recipe | **CONFIRMED** | byte-identical repack; CRC self-test + 2.9.0 vector (`STATIC_RAW`) |
| Inspected application OTA handlers use CRC-32 without an identified image signature check | **CONFIRMED for inspected paths** | handler decompilation in both builds (`STATIC_IDA`); ROM behavior is outside this evidence |
| Execution of the one-byte-modified image | **UNRESOLVED** | owner reported update success, reboot, and normal operation (`HARDWARE`); changed byte was not read back or observed at runtime |
| Tested patched-app OTA flow is not blocked by pinning | **CONFIRMED for tested flow** | no `okhttp3.CertificatePinner` references were found; a user-CA MITM worked after app trust configuration was changed (`STATIC_APP` + `HARDWARE`); other custom pinning paths not exhaustively ruled out |
| RSA-2048 in the app is anti-counterfeit, not firmware signing | **HIGH** | class/method analysis; no config signature field observed for this product (`STATIC_IDA`) |
| OTA is staged; download-phase application remains intact | **HIGH** | staging at `0x28120000` reduces risk; does not guarantee recovery from a bad activation (`STATIC_IDA`) |
| External BLE central cannot drive OTA (TWS-state gate) | **HIGH** | gate predicate + 18 call sites; standalone session stalls at config/start (`STATIC_IDA` + `HARDWARE`) |
| TOTA v2 key schedule is client-derived (no device secret) | **CONFIRMED** | handshake reproduced; device returned "connect success" (`STATIC_IDA` + `HARDWARE`) |
| Factory console exists with identity/calibration writes | **CONFIRMED** (inventory) | `factory_command_table.csv` (`STATIC_RAW` + `STATIC_IDA`) |
| Factory console reachable over the air | **UNRESOLVED** | no wireless path to the AT parser demonstrated |
| ROM secure-boot enforcement | **UNRESOLVED** | ROM not dumped; outer container format and app success do not establish bootloader behavior |
| Anti-rollback / downgrade protection | **UNRESOLVED** | none seen in the application image; ROM behavior unknown |

## What is well covered

The OTA pipeline end to end: the container format, the CRC recipe, the BLE/GATT
command protocol, the BES TOTA v2 transport, the device-side OTA command handler
and its CRC-only integrity checks, the staged-flash layout, the
app-side trust configuration, and a reproducible owner-device delivery method.

## What is partial

- The RAM map is limited to OTA-path variables (`ram_state_vars.csv`).
- The factory console is inventoried but its over-the-air reachability is open.
- The exact top of the OTA staging region is inferred, not read from a table.
- Function addresses are provided for **both** builds and mapped one-to-one in
  `generated/cross_build_map.csv`; the OTA handler/gate/CRC were re-confirmed
  identical in a direct 2.9.0 analysis.

## What is unresolved

- The modified application byte was not independently read back or observed at
  runtime; reported update success and device health do not identify which image
  executed. See [VALIDATION.md](VALIDATION.md#hardware-validation-boundary).
- The ROM / secondary bootloader (`0x000000`–`0x010000`) is outside every OTA
  image and was not dumped; any ROM-level secure-boot or rollback logic is
  therefore unproven either way.
- Audio/ANC, codec, and Bluetooth-stack function semantics (the bulk of the
  7,960 functions) are enumerated but not reverse-engineered.
- No independent second-tool (Ghidra) cross-check was run for this release.
- No UART/SWD or logic-analyzer capture; dynamic evidence is limited to
  owner-observed app/update behavior on one unit.

## Single-unit caveat

All hardware observations are from one author-owned unit on the firmware
revisions named in [PROVENANCE.md](PROVENANCE.md). Nothing here is validated on
another unit, region, or firmware revision, and firmware modification is
performed at the owner's risk (see [../SAFETY.md](../SAFETY.md)).
