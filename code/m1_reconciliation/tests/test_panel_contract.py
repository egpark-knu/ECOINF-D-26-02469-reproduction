from pathlib import Path
import hashlib
import json
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panel_contract import validate_panel


PANEL = Path(__file__).resolve().parents[3] / "data/insitu_annual_analysis_panel.csv"
EQUALITY_AUDIT = PANEL.parent / "panel_provenance_equality.json"


class PanelContractTests(unittest.TestCase):
    def test_public_panel_differs_only_in_two_provenance_columns(self):
        audit = json.loads(EQUALITY_AUDIT.read_text(encoding="utf-8"))
        panel = pd.read_csv(PANEL)
        public_hash = hashlib.sha256(PANEL.read_bytes()).hexdigest()

        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["shape"], [288, 32])
        self.assertEqual(audit["schema"], panel.columns.tolist())
        self.assertEqual(
            audit["exact_differing_columns"],
            ["first_snapshot_x", "first_snapshot_y"],
        )
        self.assertEqual(audit["differing_cell_counts"], {
            "first_snapshot_x": 288,
            "first_snapshot_y": 288,
        })
        self.assertTrue(audit["normalized_provenance_equal"])
        self.assertEqual(audit["public_file_sha256"], public_hash)
        self.assertEqual(
            audit["original_file_sha256"],
            "83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7",
        )

        public_column_hashes = {
            column: hashlib.sha256(
                pd.util.hash_pandas_object(panel[column], index=False, categorize=False).values.tobytes()
            ).hexdigest()
            for column in panel.columns
        }
        self.assertEqual(audit["public_column_hashes"], public_column_hashes)
        for column in audit["semantic_equal_columns"]:
            self.assertEqual(
                audit["original_column_hashes"][column],
                audit["public_column_hashes"][column],
            )
        for column in audit["exact_differing_columns"]:
            self.assertEqual(
                audit["normalized_provenance_hashes"][column],
                audit["public_column_hashes"][column],
            )

    def test_canonical_panel_contract(self):
        panel, audit = validate_panel(PANEL)
        self.assertEqual(panel.shape, (288, 32))
        self.assertEqual(audit["season_counts"], {
            "annual_all_samples": 144,
            "bloom_season_06_10": 144,
        })
        self.assertEqual(audit["duplicate_keys"], 0)
        self.assertEqual(audit["n_weirs"], 16)
        self.assertEqual(audit["n_years"], 9)
        self.assertEqual(audit["shared_support_counts"], {
            "annual_all_samples": 144,
            "bloom_season_06_10": 144,
        })
        self.assertEqual(audit["tau_nonpositive"], 0)
        self.assertAlmostEqual(
            audit["zscore_metadata"]["annual_all_samples"]
            ["log1p_harmful_cyanobacteria_total_mean"]["mean"],
            6.3993855337703121,
            places=12,
        )
        self.assertAlmostEqual(
            audit["zscore_metadata"]["bloom_season_06_10"]
            ["log1p_chlorophyll_a_mean"]["sd_ddof1"],
            0.60480878146693906,
            places=12,
        )


if __name__ == "__main__":
    unittest.main()
