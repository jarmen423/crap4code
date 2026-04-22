"""Tree-sitter based Rust analyzer."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Node, Parser
import tree_sitter_rust

from crap4code.core.coverage import normalize_repo_path
from crap4code.core.models import FunctionMetrics


_FUNCTION_NODES = {"function_item", "closure_expression"}


def _text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _container_for_impl(source: bytes, node: Node) -> str:
    target = _text(source, node.child_by_field_name("type")) or "module"
    trait = _text(source, node.child_by_field_name("trait"))
    return f"{target} (impl {trait})" if trait else target


def _count_complexity(source: bytes, root: Node) -> int:
    """Count Rust decision points while ignoring nested functions and closures."""

    total = 1

    def visit(node: Node) -> None:
        nonlocal total
        if node is not root and node.type in _FUNCTION_NODES:
            return

        if node.type in {"if_expression", "for_expression", "while_expression", "loop_expression"}:
            total += 1
        elif node.type == "match_expression":
            total += max(1, sum(1 for child in node.children if child.type == "match_arm"))
        elif node.type == "binary_expression":
            operators = {child.type for child in node.children if not child.is_named}
            if operators.intersection({"&&", "||"}):
                total += 1
            else:
                snippet = _text(source, node)
                if "&&" in snippet or "||" in snippet:
                    total += 1

        for child in node.children:
            if child.is_named:
                visit(child)

    visit(root)
    return total


class RustAnalyzer:
    """Analyze Rust source using the tree-sitter Rust grammar."""

    language = "rust"
    extensions = (".rs",)

    def __init__(self) -> None:
        self._parser = Parser(Language(tree_sitter_rust.language()))

    def analyze(self, root: Path, files: list[Path]) -> list[FunctionMetrics]:
        """Analyze Rust files into the shared per-function contract."""

        rows: list[FunctionMetrics] = []
        for file_path in files:
            try:
                source = file_path.read_bytes()
            except OSError:
                continue

            tree = self._parser.parse(source)
            relative_path = normalize_repo_path(file_path, root)
            rows.extend(self._collect_rows(relative_path, source, tree.root_node))
        return rows

    def _collect_rows(self, relative_path: str, source: bytes, root_node: Node) -> list[FunctionMetrics]:
        rows: list[FunctionMetrics] = []

        def walk(node: Node, container: str) -> None:
            if node.type == "impl_item":
                next_container = _container_for_impl(source, node)
                body = node.child_by_field_name("body")
                if body:
                    walk(body, next_container)
                return

            if node.type == "function_item":
                name = _text(source, node.child_by_field_name("name")) or "<anonymous>"
                body = node.child_by_field_name("body") or node
                rows.append(
                    FunctionMetrics(
                        language=self.language,
                        file_path=relative_path,
                        container=container,
                        function_name=name,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        complexity=_count_complexity(source, body),
                    )
                )

            for child in node.children:
                if child.is_named:
                    walk(child, container)

        walk(root_node, "module")
        return rows
