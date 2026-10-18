# Contributing

Contributions are welcome, including corrections — this is single-unit,
AI-assisted research (see [docs/PROVENANCE.md](docs/PROVENANCE.md)).

## Ground rules

- **Preserve build provenance.** Every address must be attributed to a build
  (the analyzed `wavebuds.elf` or the 2.9.0 package). See
  [docs/ADDRESS_LEDGER.md](docs/ADDRESS_LEDGER.md). A function VA from one build
  does not land on the same function in another.
- **Ship no firmware.** No JBL firmware, no app (original or modified), no IDA
  database with firmware bytes. See [SAFETY.md](SAFETY.md).
- **Separate facts from interpretation.** Mark unknowns `UNRESOLVED`; do not
  substitute a guess.
- **Keep generated data generated.** If you change a file in `docs/generated/`,
  regenerate it with the documented tool rather than editing it by hand, so it
  stays reproducible.

## Before opening a PR

```bash
python3 -m unittest discover -s tests
python3 -O -m unittest discover -s tests
```

Both must pass. Safety guards must never rely on `assert` (stripped under `-O`);
use explicit checks that raise.

## Scope

Static analysis, format/tooling, protocol detail, and owner-performed hardware
reports are all in scope. Security-relevant findings should follow
[SECURITY.md](SECURITY.md).
