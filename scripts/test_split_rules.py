import json
from pathlib import Path
import tempfile
import unittest

from split_rules import MANIFEST, MAX_BYTES, split_directory


class SplitRulesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "rule"
        self.directory.mkdir()

    def write(self, name, data):
        (self.directory / name).write_bytes(data)

    def test_exact_limit_and_unicode_are_split_on_line_boundaries(self):
        header = "! header\n".encode()
        lines = ["||long-example.org^\n".encode(), "||中文.example^\n".encode()]
        self.write("all-easylist.txt", header + b"".join(lines))
        limit = len(header) + len(lines[0])
        split_directory(self.directory, limit)
        self.assertEqual((self.directory / "all-easylist.txt").read_bytes(), header + lines[0])
        self.assertEqual((self.directory / "all-easylist-2.txt").read_bytes(), header + lines[1])
        self.assertLessEqual((self.directory / "all-easylist-2.txt").stat().st_size, limit)

    def test_each_clash_part_has_payload_and_stale_parts_are_removed(self):
        header = b"# header\npayload:\n"
        self.write("all-clash.yaml", header + b"  - a\n  - b\n  - c\n")
        split_directory(self.directory, len(header) + len(b"  - a\n"))
        for number in ("", "-2", "-3"):
            self.assertTrue((self.directory / f"all-clash{number}.yaml").read_bytes().startswith(header))
        self.write("all-clash.yaml", header + b"  - z\n")
        split_directory(self.directory, len(header) + len(b"  - z\n"))
        self.assertFalse((self.directory / "all-clash-2.yaml").exists())
        self.assertFalse((self.directory / "all-clash-3.yaml").exists())
        manifest = json.loads((self.directory / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(manifest["files"]["all-clash.yaml"], ["all-clash.yaml"])

    def test_rejects_oversized_rule_without_changing_original(self):
        source = b"! header\n" + b"x" * 50 + b"\n"
        self.write("all.txt", source)
        with self.assertRaisesRegex(ValueError, "Rule exceeds"):
            split_directory(self.directory, 30)
        self.assertEqual((self.directory / "all.txt").read_bytes(), source)
        self.assertFalse((self.directory / MANIFEST).exists())

    def test_rejects_missing_payload_and_filename_collisions(self):
        self.write("all-clash.yaml", b"# header\nnot-payload\n")
        with self.assertRaisesRegex(ValueError, "payload"):
            split_directory(self.directory, 50)
        (self.directory / "all-clash.yaml").unlink()
        self.write("rules.txt", b"one\ntwo\n")
        self.write("rules-2.txt", b"ok\n")
        with self.assertRaisesRegex(ValueError, "collision"):
            split_directory(self.directory, 4)
        self.assertEqual((self.directory / "rules.txt").read_bytes(), b"one\ntwo\n")

    def test_real_7mb_limit_includes_header(self):
        header = b"# header\n"
        line = b"x" * 999 + b"\n"
        self.write("rules.txt", header + line * 7001)
        split_directory(self.directory)
        first = self.directory / "rules.txt"
        second = self.directory / "rules-2.txt"
        self.assertLessEqual(first.stat().st_size, MAX_BYTES)
        self.assertLessEqual(second.stat().st_size, MAX_BYTES)
        self.assertEqual(first.read_bytes()[len(header):] + second.read_bytes()[len(header):], line * 7001)


if __name__ == "__main__":
    unittest.main()
