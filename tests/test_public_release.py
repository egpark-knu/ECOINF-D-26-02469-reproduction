import tempfile
import unittest
from pathlib import Path

import verify_public_release as verifier


ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseContractTests(unittest.TestCase):
    def test_current_tree_satisfies_public_release_contract(self):
        result = verifier.verify_release(ROOT, check_manifest=False)
        self.assertEqual([], result["failures"], result)

    def test_forbidden_path_scanner_detects_constructed_fixture(self):
        forbidden = "/" + "Users" + "/person/private.csv"
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.txt"
            fixture.write_text(forbidden, encoding="utf-8")
            hits = verifier.scan_paths([fixture], base=Path(directory))
        self.assertEqual(1, len(hits))
        self.assertEqual("local_home_path", hits[0]["pattern"])


if __name__ == "__main__":
    unittest.main()
