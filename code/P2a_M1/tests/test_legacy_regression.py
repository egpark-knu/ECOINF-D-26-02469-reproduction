from pathlib import Path
import hashlib
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legacy_adapter import _load_vendor


ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "code/P2a_M1/vendor/hardening_specificity_analysis__c895385a.py"
PANEL = ROOT / "data/insitu_annual_analysis_panel.csv"
LEGACY = ROOT / "data/P2a_M1/runs/20260815T042826Z_c2ac8933/legacy"
MODELS = LEGACY / "standardized_tau_models.csv"
INTERACTION = LEGACY / "specificity_interaction.csv"


class LegacyRegressionAnchorTests(unittest.TestCase):
    def test_vendor_hash(self):
        self.assertEqual(
            hashlib.sha256(VENDOR.read_bytes()).hexdigest(),
            "29f46b586460bf478e1c512683cdb07ce6e6b6f5b53a85857e2ba2967a1a833f",
        )

    def test_vendor_import_supports_dataclass_module_lookup(self):
        module = _load_vendor(VENDOR)
        self.assertTrue(hasattr(module, "Fit"))
        self.assertTrue(callable(module.make_model_outputs))

    def test_historical_targets_exist(self):
        models = pd.read_csv(MODELS)
        inter = pd.read_csv(INTERACTION)
        primary = models[models["model_family"] == "z_standardized_log1p_outcome"]
        target = {
            ("annual_all_samples", "cyano"): 0.6874057079174496,
            ("annual_all_samples", "chlorophyll_a"): 0.14757774021651276,
            ("bloom_season_06_10", "cyano"): 0.6186412520414742,
            ("bloom_season_06_10", "chlorophyll_a"): 0.3216193241323556,
        }
        for key, expected in target.items():
            row = primary[(primary["season_scope"] == key[0]) & (primary["outcome"] == key[1])]
            self.assertEqual(len(row), 1)
            self.assertAlmostEqual(float(row.iloc[0]["beta_log1p_tau"]), expected, places=12)
        self.assertAlmostEqual(
            float(inter.loc[inter["season_scope"] == "annual_all_samples", "interaction_beta_cyano_minus_chla"].iloc[0]),
            0.887440253669714,
            places=12,
        )
        self.assertAlmostEqual(
            float(inter.loc[inter["season_scope"] == "bloom_season_06_10", "interaction_beta_cyano_minus_chla"].iloc[0]),
            1.0350637385933135,
            places=12,
        )

    def test_bloom_cluster_se_index_alignment_defect_is_isolated_to_uncertainty(self):
        module = _load_vendor(VENDOR)
        panel = pd.read_csv(PANEL)

        annual = module.one_outcome_frame(panel, "annual_all_samples", "cyano", True)
        bloom = module.one_outcome_frame(panel, "bloom_season_06_10", "cyano", True)
        annual_groups = pd.Series(range(len(annual))).groupby(
            annual["weir_name"].astype(str)
        ).groups
        bloom_groups = pd.Series(range(len(bloom))).groupby(
            bloom["weir_name"].astype(str)
        ).groups

        self.assertEqual((int(annual.index.min()), int(annual.index.max())), (0, 143))
        self.assertEqual((int(bloom.index.min()), int(bloom.index.max())), (144, 287))
        self.assertEqual(len(annual_groups), 16)
        self.assertEqual(len(bloom_groups), 0)

        old = module.ols_fit(
            bloom,
            "outcome_value",
            ["log1p_tau"],
            ["weir_name", "year"],
            "log1p_tau",
        )
        reset = module.ols_fit(
            bloom.reset_index(drop=True),
            "outcome_value",
            ["log1p_tau"],
            ["weir_name", "year"],
            "log1p_tau",
        )
        self.assertEqual(old.se_cluster, 0.0)
        self.assertGreater(reset.se_cluster, 0.0)
        self.assertAlmostEqual(old.beta, reset.beta, places=15)


if __name__ == "__main__":
    unittest.main()
