import unittest
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_p2d import _attempt_model_row, _m9_verdict, assert_output_jail


class RunnerAxisTests(unittest.TestCase):
    def test_output_jail_normalizes_relative_allowed_path_before_parent_walk(self):
        with tempfile.TemporaryDirectory() as directory:
            allowed = Path(directory) / "P2d"
            target = allowed / "runs/unit_test_not_created"
            with patch("pathlib.Path.mkdir") as mkdir:
                resolved = assert_output_jail(target, allowed)
        self.assertTrue(resolved.is_absolute())
        self.assertEqual(resolved.name, "unit_test_not_created")
        mkdir.assert_called_once_with(parents=True)

    def test_failed_model_is_recorded_without_fabricated_estimate(self):
        frame = pd.DataFrame({"weir_name": ["w"], "occurrence": [1.0]})
        with patch("run_p2d._model_row", side_effect=ValueError("logit failed to converge")):
            row = _attempt_model_row(frame, "primary_june_october", "occurrence", False)
        self.assertEqual(row["model_status"], "HALTED")
        self.assertEqual(row["error_type"], "ValueError")
        self.assertIn("failed to converge", row["error_message"])
        self.assertTrue(np.isnan(row["coefficient_log2_tau"]))

    def test_primary_halt_forces_axis_exhausted(self):
        models = pd.DataFrame(
            [
                {
                    "window": "primary_june_october",
                    "part": "occurrence",
                    "calendar_balanced": False,
                    "model_status": "HALTED",
                    "coefficient_log2_tau": np.nan,
                    "p_holm_primary_family": np.nan,
                },
                {
                    "window": "primary_june_october",
                    "part": "positive",
                    "calendar_balanced": False,
                    "model_status": "FIT",
                    "coefficient_log2_tau": 0.5,
                    "p_holm_primary_family": np.nan,
                },
            ]
        )
        verdict, reason = _m9_verdict(models)
        self.assertEqual(verdict, "AXIS_EXHAUSTED")
        self.assertIn("primary", reason.lower())


if __name__ == "__main__":
    unittest.main()
