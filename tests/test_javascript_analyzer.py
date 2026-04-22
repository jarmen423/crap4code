"""JavaScript and TypeScript analyzer tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from crap4code.languages.javascript.analyzer import JavaScriptFamilyAnalyzer


class JavaScriptAnalyzerTests(unittest.TestCase):
    """Validate parser-backed JS/TS function discovery."""

    def test_javascript_extracts_exported_class_and_object_methods(self) -> None:
        source = textwrap.dedent(
            """
            export async function fetchThing(x) {
              if (x) return 1;
              return 0;
            }

            class Demo {
              run() {
                if (true) return 1;
                return 0;
              }
            }

            const obj = {
              method(y) {
                while (y) {
                  return y;
                }
              }
            };
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.js"
            file_path.write_text(source, encoding="utf-8")
            rows = JavaScriptFamilyAnalyzer("javascript").analyze(root=Path(tmpdir), files=[file_path])

        names = {row.function_name for row in rows}
        self.assertEqual(names, {"fetchThing", "run", "method"})
        self.assertEqual(next(row for row in rows if row.function_name == "run").container, "Demo")
        self.assertEqual(next(row for row in rows if row.function_name == "method").container, "obj")

    def test_typescript_extracts_arrow_functions(self) -> None:
        source = textwrap.dedent(
            """
            const typed = async (x: number): Promise<number> => {
              return x ? 1 : 0;
            };
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.ts"
            file_path.write_text(source, encoding="utf-8")
            rows = JavaScriptFamilyAnalyzer("typescript").analyze(root=Path(tmpdir), files=[file_path])

        self.assertEqual([row.function_name for row in rows], ["typed"])
        self.assertGreaterEqual(rows[0].complexity, 2)


if __name__ == "__main__":
    unittest.main()
