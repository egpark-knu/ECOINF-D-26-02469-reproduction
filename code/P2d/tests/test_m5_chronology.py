import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m5_chronology import chronology_eligibility


class ChronologyGateTests(unittest.TestCase):
    def _complete_inputs(self):
        weirs = ["a", "b", "c", "d"]
        events = pd.DataFrame(
            {
                "weir_name": weirs,
                "start_date": ["2019-01-01"] * 4,
                "end_date": ["2021-12-31"] * 4,
                "date_precision": ["exact_day"] * 4,
                "analysis_usable": ["final_sequence"] * 4,
            }
        )
        coverage = pd.DataFrame(
            {
                "weir_name": weirs,
                "current_best_status": ["final_sequence"] * 4,
                "final_timeline_blocker": [""] * 4,
            }
        )
        gaps = pd.DataFrame(
            {
                "weir_name": [w for w in weirs for _ in range(9)],
                "year": list(range(2017, 2026)) * 4,
                "audit_status": ["final_daily_sequence"] * 36,
                "analysis_use": ["event_time_ready"] * 36,
            }
        )
        panel = pd.DataFrame(
            {
                "weir_name": weirs,
                "river": ["r1", "r1", "r2", "r2"],
                "gate0_group": ["treated", "control", "treated", "control"],
            }
        )
        return events, coverage, gaps, panel

    def test_accepts_complete_exact_sequence_within_basin_support(self):
        result = chronology_eligibility(*self._complete_inputs())
        self.assertTrue(result["eligible"])
        self.assertEqual(result["unresolved_weirs"], [])

    def test_rejects_open_ended_and_cross_basin_chronology(self):
        events, coverage, gaps, panel = self._complete_inputs()
        events.loc[events["weir_name"] == "a", "end_date"] = ""
        coverage.loc[coverage["weir_name"] == "a", "final_timeline_blocker"] = "open ended"
        panel["river"] = ["r1", "r2", "r2", "r2"]
        panel["gate0_group"] = ["treated", "control", "control", "control"]
        result = chronology_eligibility(events, coverage, gaps, panel)
        self.assertFalse(result["eligible"])
        self.assertIn("a", result["unresolved_weirs"])
        self.assertIn("no_within_basin_treated_control_variation", result["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
