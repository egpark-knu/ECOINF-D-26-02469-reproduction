from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panel_contract import validate_new_root


class OutputJailTests(unittest.TestCase):
    def test_accepts_fresh_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "allowed"
            allowed.mkdir()
            candidate = allowed / "fresh"
            self.assertEqual(validate_new_root(candidate, allowed), candidate.resolve())

    def test_rejects_escape_and_existing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "allowed"
            allowed.mkdir()
            with self.assertRaises(ValueError):
                validate_new_root(Path(tmp) / "outside", allowed)
            existing = allowed / "existing"
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                validate_new_root(existing, allowed)

    def test_rejects_symlink_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "allowed"
            allowed.mkdir()
            real = allowed / "real"
            real.mkdir()
            link = allowed / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_new_root(link / "fresh", allowed)


if __name__ == "__main__":
    unittest.main()
