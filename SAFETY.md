# Safety policy

This project uses a strict evidence hierarchy:

1. A string is only a lead.
2. A referenced descriptor or table entry proves that data is used.
3. A reachable handler proves that an action exists.
4. A device-side path and payload validation are required before calling an
   action usable.
5. A change is not releasable until its exact decompressed-byte diff, the
   recomputed container CRC-32, the parser/length constraints, and the relevant
   device handler path are all understood and tested.

## Non-negotiable rules for firmware modification

- Never flash an image built for a different model, PID, region, or firmware
  build. Derive only from the **current** official package for your own unit.
- Always recompute the container CRC-32 after any change (`ota_repack.py` does
  this and refuses a non-identity round-trip).
- Validate the whole pipeline with the **unchanged** official image first; only
  then send a modified one.
- Do not downgrade. The app gates on advertised version and the device activates
  what it is given.
- During transfer, keep both earbuds out of the case and near the phone. Do not
  interrupt a transfer that is advancing.
- A frozen progress indicator is not permission to power-cycle aggressively; let
  the device settle and retry the normal flow.
- Do not write factory identity or calibration values (MAC, BLE address, crystal
  trim) without recording every original value first. A wrong trim degrades RF.
- Do not expose factory-console writes as routine actions; their reachability and
  side effects are not fully resolved (see
  [docs/10-factory-console.md](docs/10-factory-console.md)).

## Recovery limitation

No external programmer or exposed USB/DFU recovery path was surfaced for the
BES1306 on this unit. The OTA download phase is staged and brick-safe, but the
post-reboot activation of a **CRC-valid but functionally broken** image has no
observed rollback path. Treat every flash as irreversible.

## No firmware or app redistribution

Do not commit JBL `.bin` firmware, the JBL app (original or modified), extracted
proprietary payloads, or an IDA database containing firmware bytes. Publish
hashes, offsets, original/target bytes, independently written analysis, and
scripts instead.
