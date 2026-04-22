"""Rust analyzer tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from crap4code.languages.rust.analyzer import RustAnalyzer


class RustAnalyzerTests(unittest.TestCase):
    """Validate parser-backed Rust function discovery."""

    def test_extracts_impl_and_trait_impl_containers(self) -> None:
        source = textwrap.dedent(
            """
            pub async fn free_run(x: i32) -> i32 {
                if x > 0 { 1 } else { 0 }
            }

            impl<T> Service<T> {
                pub async fn run(&self) {
                    if true && true {}
                }
            }

            impl Worker for Service {
                fn work(&self) {
                    match 1 { 1 => (), _ => () }
                }
            }
            """
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.rs"
            file_path.write_text(source, encoding="utf-8")
            rows = RustAnalyzer().analyze(root=Path(tmpdir), files=[file_path])

        self.assertEqual({row.function_name for row in rows}, {"free_run", "run", "work"})
        self.assertEqual(next(row for row in rows if row.function_name == "run").container, "Service<T>")
        self.assertEqual(
            next(row for row in rows if row.function_name == "work").container,
            "Service (impl Worker)",
        )


if __name__ == "__main__":
    unittest.main()
