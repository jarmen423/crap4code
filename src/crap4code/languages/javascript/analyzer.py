"""Tree-sitter based JavaScript and TypeScript analyzer."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Node, Parser
import tree_sitter_javascript
import tree_sitter_typescript

from crap4code.core.coverage import normalize_repo_path
from crap4code.core.models import FunctionMetrics


_FUNCTION_NODES = {
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
}
_DECISION_NODES = {
    "if_statement",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "catch_clause",
    "conditional_expression",
    "ternary_expression",
}


def _text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _first_named_child(node: Node, node_type: str) -> Node | None:
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _binary_operator_cost(source: bytes, node: Node) -> int:
    if node.type != "binary_expression":
        return 0
    operators = {child.type for child in node.children if not child.is_named}
    if operators.intersection({"&&", "||", "??"}):
        return 1
    snippet = _text(source, node)
    return 1 if "&&" in snippet or "||" in snippet or "??" in snippet else 0


def _count_complexity(source: bytes, root: Node) -> int:
    """Count branching within one function body while skipping nested functions."""

    total = 1

    def visit(node: Node) -> None:
        nonlocal total
        if node is not root and node.type in _FUNCTION_NODES:
            return

        if node.type in _DECISION_NODES:
            total += 1
        elif node.type == "switch_body":
            total += sum(1 for child in node.children if child.type in {"switch_case", "switch_default"})
        else:
            total += _binary_operator_cost(source, node)

        for child in node.children:
            if child.is_named:
                visit(child)

    visit(root)
    return total


def _class_name(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return _text(source, name_node)
    return None


def _variable_name(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return _text(source, name_node)
    return None


def _method_name(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return _text(source, name_node)
    return None


class JavaScriptFamilyAnalyzer:
    """Analyze JS or TS source with the language-appropriate grammar."""

    def __init__(self, language: str) -> None:
        self.language = language
        self.extensions = (".ts", ".tsx") if language == "typescript" else (".js", ".jsx", ".mjs", ".cjs")
        grammar = (
            Language(tree_sitter_typescript.language_typescript())
            if language == "typescript"
            else Language(tree_sitter_javascript.language())
        )
        self._parser = Parser(grammar)

    def analyze(self, root: Path, files: list[Path]) -> list[FunctionMetrics]:
        """Analyze JS or TS files into the shared per-function contract."""

        rows: list[FunctionMetrics] = []
        for file_path in files:
            try:
                source = file_path.read_bytes()
            except OSError:
                continue

            tree = self._parser.parse(source)
            relative_path = normalize_repo_path(file_path, root)
            rows.extend(self._collect_file_rows(relative_path, source, tree.root_node))
        return rows

    def _collect_file_rows(self, relative_path: str, source: bytes, root_node: Node) -> list[FunctionMetrics]:
        rows: list[FunctionMetrics] = []

        def walk(node: Node, container_stack: list[str]) -> None:
            if node.type == "class_declaration":
                class_name = _class_name(node, source)
                next_stack = container_stack + ([class_name] if class_name else [])
                for child in node.children:
                    if child.is_named:
                        walk(child, next_stack)
                return

            if node.type == "variable_declarator":
                variable_name = _variable_name(node, source)
                value_node = node.child_by_field_name("value")
                if value_node and value_node.type == "object" and variable_name:
                    walk(value_node, container_stack + [variable_name])
                    return

                if value_node and value_node.type in {"arrow_function", "function_expression"} and variable_name:
                    rows.append(
                        self._row_from_callable(
                            relative_path=relative_path,
                            source=source,
                            node=value_node,
                            function_name=variable_name,
                            container=container_stack[-1] if container_stack else "module",
                        )
                    )
                    for child in value_node.children:
                        if child.is_named:
                            walk(child, container_stack)
                    return

            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                function_name = _text(source, name_node) or "<anonymous>"
                rows.append(
                    self._row_from_callable(
                        relative_path=relative_path,
                        source=source,
                        node=node,
                        function_name=function_name,
                        container=container_stack[-1] if container_stack else "module",
                    )
                )

            if node.type == "method_definition":
                function_name = _method_name(node, source) or "<anonymous>"
                rows.append(
                    self._row_from_callable(
                        relative_path=relative_path,
                        source=source,
                        node=node,
                        function_name=function_name,
                        container=container_stack[-1] if container_stack else "module",
                    )
                )

            for child in node.children:
                if child.is_named:
                    walk(child, container_stack)

        walk(root_node, [])
        return rows

    def _row_from_callable(
        self,
        *,
        relative_path: str,
        source: bytes,
        node: Node,
        function_name: str,
        container: str,
    ) -> FunctionMetrics:
        body = node.child_by_field_name("body") or node
        return FunctionMetrics(
            language=self.language,
            file_path=relative_path,
            container=container or "module",
            function_name=function_name,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            complexity=_count_complexity(source, body),
        )
