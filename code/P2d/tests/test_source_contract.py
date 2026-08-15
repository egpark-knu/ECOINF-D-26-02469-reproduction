import hashlib
import unittest
from pathlib import Path

import pandas as pd


CYANO = Path(
    "/Users/eungyupark/Dropbox/Manuscripts/0_HAB/Round_6/01_data/insitu/"
    "cyanobacteria_panel.csv"
)
PROXY = Path(
    "/Users/eungyupark/Dropbox/Manuscripts/0_HAB/Round_6/02_analysis/proxy_validation/"
    "insitu_annual_analysis_panel.csv"
)


class SourceContractTests(unittest.TestCase):
    def test_frozen_source_hashes(self):
        self.assertEqual(
            hashlib.sha256(CYANO.read_bytes()).hexdigest(),
            "c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b",
        )
        self.assertEqual(
            hashlib.sha256(PROXY.read_bytes()).hexdigest(),
            "83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7",
        )

    def test_expected_source_schemas(self):
        cyano = pd.read_csv(CYANO, nrows=0)
        proxy = pd.read_csv(PROXY, nrows=0)
        self.assertTrue(
            {"station_code", "sampling_date", "variable", "source_field", "unit", "value"}
            <= set(cyano.columns)
        )
        self.assertTrue(
            {"weir_name", "year", "tau_days", "ndci_mean", "season_scope"}
            <= set(proxy.columns)
        )


if __name__ == "__main__":
    unittest.main()
