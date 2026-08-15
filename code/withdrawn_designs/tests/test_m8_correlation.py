import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m8_correlation import (
    dependent_correlation_analysis,
    relationship_form_diagnostics,
    paired_common_support,
    within_between_correlations,
)


class DependentCorrelationTests(unittest.TestCase):
    def synthetic(self):
        rng = np.random.default_rng(41)
        rows = []
        for cluster in range(8):
            shift = cluster / 5
            for year in range(7):
                x = shift + year / 9 + rng.normal(0, 0.05)
                rows.append(
                    {
                        "weir_name": f"w{cluster}",
                        "year": 2017 + year,
                        "ndci": x,
                        "cyano": 0.15 * x + rng.normal(0, 0.8),
                        "chla": 1.2 * x + rng.normal(0, 0.08),
                    }
                )
        return pd.DataFrame(rows)

    def test_common_support_is_paired(self):
        frame = self.synthetic()
        frame.loc[0, "cyano"] = np.nan
        frame.loc[1, "chla"] = np.nan
        common = paired_common_support(frame, ["ndci", "cyano", "chla", "weir_name", "year"])
        self.assertEqual(len(common), len(frame) - 2)
        self.assertFalse(common[["ndci", "cyano", "chla"]].isna().any().any())

    def test_exact_signflip_and_paired_bootstrap_counts(self):
        result, patterns, bootstrap = dependent_correlation_analysis(
            self.synthetic(),
            x_col="ndci",
            cyano_col="cyano",
            chla_col="chla",
            cluster_col="weir_name",
            bootstrap_draws=199,
            seed=13,
        )
        self.assertGreater(result["spearman_delta_chla_minus_cyano"], 0)
        self.assertEqual(len(patterns), 2 ** 8)
        self.assertEqual(patterns["pattern_id"].nunique(), 2 ** 8)
        self.assertTrue(patterns["finite"].all())
        self.assertEqual(len(bootstrap), 199)
        self.assertTrue(bootstrap["finite"].all())

    def test_within_between_outputs_all_components(self):
        out = within_between_correlations(
            self.synthetic(), "ndci", "cyano", "chla", "weir_name"
        )
        self.assertEqual(set(out["component"]), {"pooled", "within_weir", "between_weir"})
        self.assertTrue(np.isfinite(out["spearman_delta_chla_minus_cyano"]).all())

    def test_relationship_diagnostic_compares_linear_and_quadratic_forms(self):
        out = relationship_form_diagnostics(
            self.synthetic(), "ndci", ["cyano", "chla"]
        )
        self.assertEqual(set(out["outcome"]), {"cyano", "chla"})
        self.assertTrue((out["quadratic_r2"] >= out["linear_r2"] - 1e-12).all())


if __name__ == "__main__":
    unittest.main()
