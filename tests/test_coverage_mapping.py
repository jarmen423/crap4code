"""Coverage mapping tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from crap4code.core.coverage import load_coverage_database


class CoverageMappingTests(unittest.TestCase):
    """Validate file-based coverage adapters."""

    def test_coverage_xml_maps_python_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = root / "coverage.xml"
            report.write_text(
                textwrap.dedent(
                    """\
                    <?xml version="1.0" ?>
                    <coverage>
                      <packages>
                        <package name="src">
                          <classes>
                            <class name="sample" filename="src/sample.py">
                              <lines>
                                <line number="10" hits="1"/>
                                <line number="11" hits="0"/>
                              </lines>
                            </class>
                          </classes>
                        </package>
                      </packages>
                    </coverage>
                    """
                ),
                encoding="utf-8",
            )

            database = load_coverage_database(root=root, report_path="coverage.xml", report_format="coverage.py-xml")

        self.assertIsNotNone(database)
        state, percent = database.coverage_for("src/sample.py", 10, 11)
        self.assertEqual(state, "measured")
        self.assertEqual(percent, 50.0)

    def test_lcov_maps_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = root / "lcov.info"
            report.write_text(
                "TN:\nSF:src/sample.ts\nDA:5,1\nDA:6,0\nend_of_record\n",
                encoding="utf-8",
            )

            database = load_coverage_database(root=root, report_path="lcov.info", report_format="lcov")

        self.assertIsNotNone(database)
        state, percent = database.coverage_for("src/sample.ts", 5, 6)
        self.assertEqual(state, "measured")
        self.assertEqual(percent, 50.0)


if __name__ == "__main__":
    unittest.main()
