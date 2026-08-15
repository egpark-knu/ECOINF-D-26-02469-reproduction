import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from v4_core import (  # noqa: E402
    association,
    aggregate_daily_satellite,
    build_frequency,
    build_matchups,
    crosswalk_accounting,
    endpoint_panel,
    percentile_midrank,
    prepare_endpoint,
    run_bootstrap,
    run_leave_one_out,
)
from v4_verify import minimum_candidate_dates, report_support_semantics, scan_submission_text  # noqa: E402


class CoreInvariantTests(unittest.TestCase):
    def test_pixel_weighting_is_index_specific(self):
        rows = pd.DataFrame(
            {
                "site": ["A", "A"],
                "date": ["2020-01-01", "2020-01-01"],
                "scene_id": ["s1", "s2"],
                "PRODUCT_ID": ["p1", "p2"],
                "MGRS_TILE": ["t1", "t2"],
                "utc_timestamp": ["u1", "u2"],
                "ndci_mean": [1.0, 3.0],
                "ndci_count": [1, 3],
                "fai_mean": [10.0, 30.0],
                "fai_count": [3, 1],
            }
        )
        got = aggregate_daily_satellite(rows).iloc[0]
        self.assertAlmostEqual(got.ndci_mean, 2.5)
        self.assertAlmostEqual(got.fai_mean, 15.0)
        self.assertEqual(got.ndci_valid_pixels, 4)
        self.assertEqual(got.fai_valid_pixels, 4)

    def test_minimum_lag_tie_is_symmetric_and_unique(self):
        daily = pd.DataFrame(
            {
                "site": ["A", "A", "A"],
                "date": pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-05"]),
                "ndci_mean": [1.0, 3.0, 99.0],
                "ndci_valid_pixels": [1, 3, 100],
                "fai_mean": [2.0, 6.0, 99.0],
                "fai_valid_pixels": [3, 1, 100],
                "component_rows": [1, 1, 1],
                "scene_ids": ["s1", "s2", "s3"],
                "product_ids": ["p1", "p2", "p3"],
                "tiles": ["t1", "t2", "t3"],
                "utc_timestamps": ["u1", "u2", "u3"],
            }
        )
        insitu = pd.DataFrame(
            {
                "site": ["A"],
                "in_situ_date": pd.to_datetime(["2020-01-02"]),
                "chlorophyll_a": [1.0],
                "harmful_cyanobacteria": [2.0],
            }
        )
        got = build_matchups(daily, insitu, {"pm3": (3, 2017, 2025)})
        self.assertEqual(len(got), 1)
        self.assertEqual(got.iloc[0].tie_count, 2)
        self.assertEqual(got.iloc[0].min_abs_lag, 1)
        self.assertAlmostEqual(got.iloc[0].ndci_mean, 2.5)
        self.assertAlmostEqual(got.iloc[0].fai_mean, 3.0)
        self.assertEqual(got[["window", "site", "in_situ_date"]].duplicated().sum(), 0)

    def test_exact_endpoint_filter_and_duplicate_dedup(self):
        base = {
            "station_code": "x",
            "station_name": "X",
            "weir_name": "보",
            "sampling_date": "2020-01-01",
            "variable": "chlorophyll_a",
            "source_field": "iemChla",
            "value": 2.0,
            "unit": "mg/m3",
            "raw_snapshot_sha256": "abc",
            "source_row_locator": "b",
        }
        rows = [base, {**base, "source_row_locator": "a"}, {**base, "variable": "pH", "source_field": "iemPh", "unit": "unitless", "value": 7.0}]
        mapping = {"보": "A"}
        got, audit = endpoint_panel(pd.DataFrame(rows), "chlorophyll_a", "iemChla", "mg/m3", mapping)
        self.assertEqual(len(got), 1)
        self.assertEqual(got.iloc[0].chlorophyll_a, 2.0)
        self.assertEqual(audit["exact_duplicates_removed"], 1)

    def test_conflicting_duplicate_halts(self):
        rows = pd.DataFrame(
            {
                "station_code": ["x", "x"],
                "station_name": ["X", "X"],
                "weir_name": ["보", "보"],
                "sampling_date": ["2020-01-01", "2020-01-01"],
                "variable": ["chlorophyll_a", "chlorophyll_a"],
                "source_field": ["iemChla", "iemChla"],
                "value": [2.0, 3.0],
                "unit": ["mg/m3", "mg/m3"],
                "raw_snapshot_sha256": ["abc", "abc"],
                "source_row_locator": ["a", "b"],
            }
        )
        with self.assertRaises(ValueError):
            endpoint_panel(rows, "chlorophyll_a", "iemChla", "mg/m3", {"보": "A"})

    def test_percentile_midrank_uses_n_plus_one_and_average_ties(self):
        got = percentile_midrank(pd.Series([1.0, 2.0, 2.0]))
        np.testing.assert_allclose(got.to_numpy(), [0.25, 0.625, 0.625])

    def test_bootstrap_is_paired_and_has_requested_draws(self):
        rows = []
        for site, shift in [("A", 0), ("B", 1), ("C", 2)]:
            for i in range(4):
                rows.append(
                    {
                        "window": "pm1",
                        "site": site,
                        "in_situ_date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                        "ndci_mean": i + shift,
                        "fai_mean": 3 - i + shift,
                        "chlorophyll_a": i + 1 + shift,
                        "harmful_cyanobacteria": 4 - i + shift,
                    }
                )
        draws, _ = run_bootstrap(pd.DataFrame(rows), windows=["pm1"], b=7, seed=42)
        expected = 7 * 3 * 2 * 2 * 2
        self.assertEqual(len(draws), expected)
        self.assertEqual(draws.draw.nunique(), 7)
        estimable = draws[draws.estimable]
        self.assertTrue(np.isfinite(estimable.full_association).all())
        paired = draws.dropna(subset=["paired_delta"])
        self.assertTrue((paired.selected_common_weirs_hash_chla == paired.selected_common_weirs_hash_cyano).all())

    def test_equal_observation_cluster_resample_matches_expanded_rows(self):
        pairs = pd.DataFrame(
            {
                "window": ["pm1"] * 6,
                "site": ["A"] * 3 + ["B"] * 3,
                "in_situ_date": pd.date_range("2020-01-01", periods=6),
                "ndci_mean": [1, 2, 4, 2, 5, 7],
                "chlorophyll_a": [1, 4, 7, 2, 3, 9],
            }
        )
        prepared = prepare_endpoint(pairs, "pm1", "ndci", "chlorophyll_a", "raw_within_weir_pearson")
        got = association(prepared, "equal_per_observation", ["A", "A", "B"])
        expanded = pd.concat(
            [prepared.data[prepared.data.site == s] for s in ["A", "A", "B"]], ignore_index=True
        )
        expected = expanded.x_t.corr(expanded.y_t)
        self.assertAlmostEqual(got, expected)

    def test_loo_has_real_rows_for_every_omission(self):
        rows = []
        for site in ["A", "B", "C"]:
            for i in range(3):
                rows.append(
                    {
                        "window": "pm1",
                        "site": site,
                        "in_situ_date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                        "ndci_mean": i + (site == "B"),
                        "fai_mean": 2 - i + (site == "C"),
                        "chlorophyll_a": i + 1,
                        "harmful_cyanobacteria": 3 - i,
                    }
                )
        got = run_leave_one_out(pd.DataFrame(rows), windows=["pm1"], all_sites=["A", "B", "C"])
        self.assertGreater(len(got), 0)
        self.assertEqual(set(got.omitted_weir), {"A", "B", "C"})
        self.assertTrue(got.association.notna().any())

    def test_frequency_includes_zero_years(self):
        scenes = pd.DataFrame(
            {
                "site": ["A"], "year": [2019], "date": ["2019-01-01"],
                "scene_id": ["s"], "PRODUCT_ID": ["p"], "MGRS_TILE": ["t"],
                "ndci_count": [2], "fai_count": [3]
            }
        )
        got = build_frequency(scenes, ["A", "B"], range(2017, 2026))
        self.assertEqual(len(got), 18)
        self.assertEqual(got.query("site == 'B'").satellite_site_dates.sum(), 0)


class AuditInvariantTests(unittest.TestCase):
    def test_report_support_gate_uses_v4_count_and_rejects_legacy_numerals(self):
        good = "V4 primary ±1-day outcome-blind matchup pairs: 756. Legacy diagnostics are invalid."
        bad = good + " Old 754-match and 233-zero values."
        self.assertTrue(report_support_semantics(good, 756))
        self.assertFalse(report_support_semantics(bad, 756))

    def test_minimum_candidate_recheck_handles_nonconsecutive_index(self):
        candidates = pd.Series(pd.to_datetime(["2020-01-01", "2020-01-03"]), index=[5, 9])
        minimum, dates = minimum_candidate_dates(candidates, pd.Timestamp("2020-01-02"), 1)
        self.assertEqual(minimum, 1)
        self.assertEqual(dates, {"2020-01-01", "2020-01-03"})

    def test_crosswalk_exact_closure(self):
        rows = [
            {
                "direct_validation_bucket_v6": "exclude" if index < 25 else "context_only",
                "direct_validation_claim_allowed_v6": False,
                "directed_network_available_v6": False,
            }
            for index in range(32)
        ]
        got = crosswalk_accounting(pd.DataFrame(rows))
        self.assertEqual(got["total_rows"], 32)
        self.assertEqual(got["bucket_counts"], {"exclude": 25, "context_only": 7})
        self.assertEqual(got["direct_validation_allowed"], 0)
        self.assertEqual(got["directed_network_available"], 0)

    def test_submission_scan_rejects_local_paths_and_semantic_overclaim(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.md"
            local_path = "/" + "Users" + "/person/data"
            p.write_text(local_path + " below detection hydrologically disconnected", encoding="utf-8")
            failures = scan_submission_text([p])
            self.assertTrue(any("local_path" in x for x in failures))
            self.assertTrue(any("forbidden_semantic" in x for x in failures))


if __name__ == "__main__":
    unittest.main()
