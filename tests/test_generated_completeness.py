"""Every shipped generated artifact must be present and non-empty."""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

GENERATED = Path(__file__).resolve().parents[1] / "docs" / "generated"

CSVS = [
    "factory_command_table.csv",
    "ota_container_layout.csv",
    "analyzed_functions.csv",
    "ram_state_vars.csv",
    "string_anchors.csv",
    "crc_test_vectors.csv",
    "cross_build_map.csv",
]


class GeneratedCompletenessTests(unittest.TestCase):
    def test_csvs_have_header_and_rows(self) -> None:
        for name in CSVS:
            path = GENERATED / name
            self.assertTrue(path.is_file(), f"missing {name}")
            with path.open(newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertGreaterEqual(len(rows), 2, f"{name} has no data rows")
            self.assertTrue(all(rows[0]), f"{name} has an empty header cell")

    def test_package_inventory_keys(self) -> None:
        inventory = json.loads((GENERATED / "package_inventory.json").read_text())
        for key in ("packaged_size", "package_sha256", "stream_count", "crc_stored", "crc_valid"):
            self.assertIn(key, inventory)
        self.assertTrue(inventory["crc_valid"])

    def test_container_layout_has_eight_streams(self) -> None:
        with (GENERATED / "ota_container_layout.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)


if __name__ == "__main__":
    unittest.main()
