<!-- Contributions must preserve build provenance and ship no firmware. -->

## Summary

What this change adds or corrects.

## Evidence

- Build attribution (analyzed `wavebuds.elf` or 2.9.0 package):
- Addresses / offsets / hashes:
- How it was verified (round-trip, decompilation, xref, hardware):

## Checklist

- [ ] No JBL firmware, app, modified APK, or IDA database with firmware bytes is included.
- [ ] Every address is attributed to a specific build.
- [ ] Observed facts are separated from interpretation; unknowns are `UNRESOLVED`, not guessed.
- [ ] `python -m unittest discover -s tests` and `python -O -m unittest discover -s tests` pass.
- [ ] Generated CSVs (if changed) were regenerated with the documented tool, not edited by hand.
