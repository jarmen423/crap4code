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

    def test_coverage_for_case_insensitive_fallback(self) -> None:
        """Reproduces "Src/Foo.py" (source discovery) vs "src/foo.py" (in report).

        This is the exact scenario from R1 / phase1-r1 and the plan verification
        criteria. The case-fold fallback inside CoverageDatabase.coverage_for
        (combined with passing the warnings list from _apply_coverage) must
        produce "measured" + correct percentage and record a warning that will
        flow into build_report / ScanReport.warnings and be printed by the CLI.

        The test exercises the new warnings= parameter (existing tests continue
        to work because it defaults to None).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = root / "coverage.xml"
            # Report uses lowercase path (common from coverage tooling / lcov / XML writers)
            report.write_text(
                textwrap.dedent(
                    """\
                    <?xml version="1.0" ?>
                    <coverage>
                      <packages>
                        <package name="src">
                          <classes>
                            <class name="foo" filename="src/foo.py">
                              <lines>
                                <line number="10" hits="1"/>
                                <line number="11" hits="1"/>
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

            database = load_coverage_database(
                root=root, report_path="coverage.xml", report_format="coverage.py-xml"
            )
            self.assertIsNotNone(database)

            # "Source" path uses different casing, as produced by discover_source_files
            # + Path.resolve() on a case-insensitive filesystem (or mixed tooling).
            warnings: list[str] = []
            state, percent = database.coverage_for("Src/Foo.py", 10, 11, warnings)

            self.assertEqual(state, "measured")
            self.assertEqual(percent, 100.0)
            self.assertGreaterEqual(len(warnings), 1)
            self.assertIn("Case-insensitive coverage path match used", warnings[0])
            self.assertIn("Src/Foo.py", warnings[0])
            self.assertIn("src/foo.py", warnings[0])

            # Original casing key still works directly (no warning emitted for it)
            w2: list[str] = []
            state2, p2 = database.coverage_for("src/foo.py", 10, 11, w2)
            self.assertEqual(state2, "measured")
            self.assertEqual(p2, 100.0)
            self.assertEqual(len(w2), 0)


if __name__ == "__main__":
    unittest.main()
