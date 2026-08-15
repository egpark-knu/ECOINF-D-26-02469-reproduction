import unittest
import warnings
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m9_hurdle import (
    aggregate_calendar_cells,
    fit_logit_cluster,
    fit_ols_cluster,
    holm_adjust,
    make_fe_design,
    prepare_harmful_panel,
)


class HurdleModelTests(unittest.TestCase):
    def synthetic_model_frame(self):
        rng = np.random.default_rng(52)
        rows = []
        for weir in range(10):
            for year in range(5):
                x = -1 + 0.45 * year + rng.normal(0, 0.1)
                for month in [6, 7, 8, 9, 10]:
                    for rep in range(3):
                        p = 1 / (1 + np.exp(-(-0.4 + 1.1 * x)))
                        occurrence = rng.binomial(1, p)
                        positive_log = 2.0 + 0.7 * x + rng.normal(0, 0.25)
                        rows.append(
                            {
                                "weir_name": f"w{weir}",
                                "sampling_year": 2017 + year,
                                "sampling_month": month,
                                "log2_tau": x,
                                "occurrence": occurrence,
                                "positive_log": positive_log,
                            }
                        )
        return pd.DataFrame(rows)

    def test_cluster_models_recover_positive_effects(self):
        frame = self.synthetic_model_frame()
        x, names = make_fe_design(
            frame, "log2_tau", ["weir_name", "sampling_year", "sampling_month"]
        )
        logit = fit_logit_cluster(frame["occurrence"].to_numpy(float), x, frame["weir_name"], names)
        positive = fit_ols_cluster(frame["positive_log"].to_numpy(float), x, frame["weir_name"], names)
        self.assertGreater(logit["coef"]["log2_tau"], 0)
        self.assertGreater(positive["coef"]["log2_tau"], 0)
        self.assertGreater(logit["se_cluster"]["log2_tau"], 0)
        self.assertGreater(positive["se_cluster"]["log2_tau"], 0)

    def test_prepare_rejects_duplicate_measurement_keys(self):
        raw = pd.DataFrame(
            {
                "station_code": ["s", "s"],
                "sampling_date": ["2020-06-01", "2020-06-01"],
                "variable": ["harmful_cyanobacteria_total"] * 2,
                "source_field": ["iemBgalageCellCo"] * 2,
                "unit": ["Cells/100mL"] * 2,
                "weir_name": ["w", "w"],
                "sampling_year": [2020, 2020],
                "sampling_month": [6, 6],
                "value": [0, 1],
            }
        )
        tau = pd.DataFrame({"weir_name": ["w"], "year": [2020], "tau_days": [2.0]})
        with self.assertRaises(ValueError):
            prepare_harmful_panel(raw, tau)

    def test_prepare_collapses_exact_api_duplicate_items(self):
        raw = pd.DataFrame(
            {
                "station_code": ["s", "s"],
                "sampling_date": ["2020-06-01", "2020-06-01"],
                "variable": ["harmful_cyanobacteria_total"] * 2,
                "source_field": ["iemBgalageCellCo"] * 2,
                "unit": ["Cells/100mL"] * 2,
                "weir_name": ["w", "w"],
                "sampling_year": [2020, 2020],
                "sampling_month": [6, 6],
                "value": [0, 0],
                "source_row_locator": ["raw#item[10]", "raw#item[11]"],
            }
        )
        tau = pd.DataFrame({"weir_name": ["w"], "year": [2020], "tau_days": [2.0]})
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            result = prepare_harmful_panel(raw, tau)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["source_row_locator"], "raw#item[10]")

    def test_calendar_cells_and_holm(self):
        frame = self.synthetic_model_frame()
        frame["value"] = np.where(frame["occurrence"] == 1, np.exp(frame["positive_log"]), 0)
        cells = aggregate_calendar_cells(frame)
        self.assertEqual(
            len(cells),
            frame[["weir_name", "sampling_year", "sampling_month"]].drop_duplicates().shape[0],
        )
        self.assertTrue(cells["occurrence_share"].between(0, 1).all())
        adjusted = holm_adjust([0.03, 0.01])
        np.testing.assert_allclose(adjusted, [0.03, 0.02])


if __name__ == "__main__":
    unittest.main()
