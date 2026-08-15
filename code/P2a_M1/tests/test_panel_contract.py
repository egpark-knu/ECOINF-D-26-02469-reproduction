from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panel_contract import validate_panel


PANEL = Path(
    "/Users/eungyupark/Dropbox/Manuscripts/0_HAB/revision_1/03_analysis/"
    "input/P2a_M1/insitu_annual_analysis_panel__83fcf10f.csv"
)


class PanelContractTests(unittest.TestCase):
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
