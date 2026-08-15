import hashlib
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
PROXY = ROOT / "data/insitu_annual_analysis_panel.csv"
SOURCE_MANIFEST = ROOT / "data/withdrawn_designs/runs/20260815T051100Z_cf60c3e4/source_manifest.json"


class SourceContractTests(unittest.TestCase):
    def test_frozen_source_hashes(self):
        import json

        records = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))["sources"]
        hashes = {Path(record["path"]).name: record["sha256"] for record in records}
        self.assertEqual(
            hashes["cyanobacteria_panel.csv"],
            "c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b",
        )
        self.assertEqual(
            hashes["insitu_annual_analysis_panel.csv"],
            "83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7",
        )
        self.assertEqual(
            hashlib.sha256(PROXY.read_bytes()).hexdigest(),
            "c7c709986648dde52930da3feedba7deb27a5e347490ea31d87272936f1d68ff",
        )

    def test_expected_source_schemas(self):
        proxy = pd.read_csv(PROXY, nrows=0)
        self.assertTrue(
            {"weir_name", "year", "tau_days", "ndci_mean", "season_scope"}
            <= set(proxy.columns)
        )


if __name__ == "__main__":
    unittest.main()
