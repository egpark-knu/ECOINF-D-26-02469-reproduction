from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoint_design import endpoint_specific_design, prepare_shared_support, separate_design
from joint_inference import fit_ols_cluster


def synthetic_panel() -> pd.DataFrame:
    rows = []
    weirs = ["A", "B", "C"]
    years = [2017, 2018, 2019, 2020]
    for gi, weir in enumerate(weirs):
        for ti, year in enumerate(years):
            tau = 1.0 + gi * 1.7 + ti * 0.8 + gi * ti * 0.13
            x = np.log1p(tau)
            common = 0.2 * gi - 0.1 * ti
            cyano = 1.4 * x + common + 0.03 * gi * ti
            chla = 0.5 * x - 0.3 * gi + 0.08 * ti - 0.02 * gi * ti
            rows.append({
                "weir_name": weir,
                "year": year,
                "river": "R1" if gi < 2 else "R2",
                "tau_days": tau,
                "season_scope": "annual_all_samples",
                "log1p_harmful_cyanobacteria_total_mean": cyano,
                "log1p_chlorophyll_a_mean": chla,
            })
    return pd.DataFrame(rows)


class EndpointDesignTests(unittest.TestCase):
    def test_column_order_rank_and_reference_levels(self):
        base = prepare_shared_support(synthetic_panel(), "annual_all_samples")
        x, y, clusters, names, meta = endpoint_specific_design(base)
        self.assertEqual(names[:4], [
            "intercept", "log1p_tau", "outcome_is_cyano", "log1p_tau_x_cyano"
        ])
        self.assertEqual(meta["reference_weir"], "A")
        self.assertEqual(meta["reference_year"], "2017")
        self.assertEqual(np.linalg.matrix_rank(x), x.shape[1])
        self.assertEqual(len(y), 24)
        self.assertEqual(len(clusters), 24)

    def test_endpoint_specific_delta_equals_separate_difference(self):
        base = prepare_shared_support(synthetic_panel(), "annual_all_samples")
        sep = {}
        for endpoint in ["cyano", "chlorophyll_a"]:
            x, y, clusters, names, _ = separate_design(base, endpoint)
            sep[endpoint] = fit_ols_cluster(x, y, clusters, names).coef_by_name["log1p_tau"]
        x, y, clusters, names, _ = endpoint_specific_design(base)
        stacked = fit_ols_cluster(x, y, clusters, names)
        delta = stacked.coef_by_name["log1p_tau_x_cyano"]
        self.assertTrue(np.isclose(delta, sep["cyano"] - sep["chlorophyll_a"], atol=1e-10, rtol=1e-10))


if __name__ == "__main__":
    unittest.main()
