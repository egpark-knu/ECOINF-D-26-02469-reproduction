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

    def test_internal_orchestration_scanner_detects_names_turns_and_markers(self):
        agents = ["clau" + "de", "cod" + "ex", "a" + "gy"]
        worker_names = " ".join(f"{agent}-1" for agent in agents)
        turns = " ".join(f"T1_{agent}1_deadbeef" for agent in agents)
        completion_field = "phase_report_" + "worker" + "_done"
        completion_marker = "[" + "WORKER" + "_DONE]"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_fixture = root / "protocol.txt"
            text_fixture.write_text(
                f"Workers: {worker_names}; turns {turns}; "
                f'\"{completion_field}\": true; {completion_marker}\n',
                encoding="utf-8",
            )
            filename_fixture = root / ("T2_" + "a" + "gy2_cafebabe.json")
            filename_fixture.write_text("{}\n", encoding="utf-8")
            hits = verifier.scan_paths([text_fixture, filename_fixture], base=root)

        def count(pattern, location):
            return sum(
                hit.get("count", 1)
                for hit in hits
                if hit["pattern"] == pattern and hit["location"] == location
            )

        self.assertEqual(3, count("internal_agent_name", "content"))
        self.assertEqual(3, count("internal_turn_id", "content"))
        self.assertEqual(1, count("internal_turn_id", "filename"))
        self.assertEqual(1, count("internal_completion_field", "content"))
        self.assertEqual(1, count("internal_completion_marker", "content"))


if __name__ == "__main__":
    unittest.main()
