from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoint_design import endpoint_specific_design, prepare_shared_support, separate_design
from joint_inference import (
    apply_cluster_signs,
    fit_ols_cluster,
    paired_cluster_bootstrap,
    rademacher_signs,
)


def correlated_panel() -> pd.DataFrame:
    rows = []
    for gi, weir in enumerate([f"W{i:02d}" for i in range(16)]):
        shock = (gi - 7.5) * 0.17
        for ti, year in enumerate([2017, 2018, 2019, 2020]):
            tau = 2.0 + gi * 0.9 + ti * 0.7 + gi * ti * 0.11
            x = np.log1p(tau)
            rows.append({
                "weir_name": weir,
                "year": year,
                "river": "R",
                "tau_days": tau,
                "season_scope": "annual_all_samples",
                "log1p_harmful_cyanobacteria_total_mean": 1.2 * x + shock + 0.04 * ti * gi,
                "log1p_chlorophyll_a_mean": 0.4 * x + 0.8 * shock - 0.03 * ti * gi,
            })
    return pd.DataFrame(rows)


class JointInferenceTests(unittest.TestCase):
    def test_exact_rademacher_count(self):
        signs = rademacher_signs(16)
        self.assertEqual(signs.shape, (65536, 16))
        self.assertTrue(np.all(signs[0] == -1.0))
        self.assertTrue(np.all(signs[-1] == 1.0))
        self.assertEqual(len(np.unique(signs, axis=0)), 65536)

    def test_cluster_sign_is_shared_across_endpoint_rows(self):
        clusters = np.array(["A", "A", "B", "B", "A", "B"])
        endpoints = np.array([0, 1, 0, 1, 0, 1])
        residual = np.arange(1.0, 7.0)
        signed = apply_cluster_signs(residual, clusters, {"A": -1.0, "B": 1.0})
        self.assertTrue(np.all(signed[clusters == "A"] == -residual[clusters == "A"]))
        self.assertTrue(np.all(signed[clusters == "B"] == residual[clusters == "B"]))
        self.assertEqual(set(endpoints[clusters == "A"]), {0, 1})

    def test_unified_variance_retains_cross_endpoint_dependence(self):
        base = prepare_shared_support(correlated_panel(), "annual_all_samples")
        separate = {}
        for endpoint in ["cyano", "chlorophyll_a"]:
            x, y, clusters, names, _ = separate_design(base, endpoint)
            separate[endpoint] = fit_ols_cluster(x, y, clusters, names)
        x, y, clusters, names, _ = endpoint_specific_design(base)
        joint = fit_ols_cluster(x, y, clusters, names)
        joint_se = joint.se_by_name["log1p_tau_x_cyano"]
        independent_se = np.sqrt(
            separate["cyano"].se_by_name["log1p_tau"] ** 2
            + separate["chlorophyll_a"].se_by_name["log1p_tau"] ** 2
        )
        self.assertGreater(joint_se, 0.0)
        self.assertFalse(np.isclose(joint_se, independent_se, atol=1e-8, rtol=1e-8))

    def test_paired_bootstrap_preserves_count_and_finiteness(self):
        base = prepare_shared_support(correlated_panel(), "annual_all_samples")
        draws = paired_cluster_bootstrap(base, n_draws=9999, seed=20260630)
        self.assertEqual(len(draws), 9999)
        self.assertTrue(draws["finite"].all())
        self.assertTrue(np.isfinite(draws["difference_star"]).all())

    def test_degenerate_small_cluster_draw_is_flagged_not_dropped(self):
        panel = correlated_panel()
        panel = panel[panel["weir_name"].isin(["W00", "W01"])].copy()
        base = prepare_shared_support(panel, "annual_all_samples")
        draws = paired_cluster_bootstrap(base, n_draws=100, seed=20260630)
        self.assertEqual(len(draws), 100)
        self.assertGreater(int((~draws["finite"]).sum()), 0)


if __name__ == "__main__":
    unittest.main()
