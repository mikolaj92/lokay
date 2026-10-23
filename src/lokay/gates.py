import ast
import io
import re
import tokenize
from pathlib import Path

from lokay.scope import is_test
from lokay.types import Finding, parse_finding


def named_test(path, body):
    return any(re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w./-])", body)
               for name in (path, Path(path).name))


def gate_contract(paths, body) -> str:
    allowed = ", ".join(sorted(path for path in paths if is_test(path) and named_test(path, body)))
    return "\n".join((
        "=== GATE CONTRACT (lokay; overrides the issue where they conflict) ===",
        "Existing test files you may change: " + (allowed or "none"),
        "In those files the number of assertion lines must not drop; replace each outdated assertion with its own equivalent assertion of the current behaviour; never merge, delete or skip assertions.",
        "Do not change, delete, rename or skip any other existing test file, even if the issue asks for it; if the issue's change would require that, implement the rest and report it as a blocker.",
        "Do not add or edit comments or docstrings in code; where the issue asks to fix a comment or docstring, delete it instead.",
        "=== END GATE CONTRACT ===",
    ))


def gate_rows(rows):
    if not rows:
        return False
    for row in rows:
        item = parse_finding(row)
        kind = item.lens or row.get("name")
        if not isinstance(item, Finding) or kind not in {
            "no_new_comments", "weakened_tests", "junk", "no_unit_tests",
        }:
            return False
        if kind == "no_new_comments" and not re.search(r"\b(?:comments?|docstrings?)\b", item.zmiana, re.I):
            return False
    return True


def gate_location(row):
    item = parse_finding(row)
    line = item.linia_od or (row.get("linie") or [1])[0] or 1
    return item.plik, int(line), item.lens or row.get("name")


def remove_comment(source, line, python):
    lines = source.splitlines(keepends=True)
    if python:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if ast.get_docstring(node, clean=False) is None:
                continue
            statement = node.body[0]
            if statement.lineno <= line <= statement.end_lineno:
                start, end = statement.lineno - 1, statement.end_lineno - 1
                prefix = lines[start].encode()[:statement.col_offset].decode()
                suffix = lines[end].encode()[statement.end_col_offset:].decode()
                replacement = "pass" if len(node.body) == 1 and not isinstance(node, ast.Module) else ""
                if suffix.lstrip().startswith(";"):
                    suffix = suffix.lstrip()[1:]
                    replacement = replacement or "pass"
                if prefix.strip():
                    replacement = replacement or "pass"
                lines[start:end + 1] = [prefix + replacement + suffix]
                return "".join(lines)
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and token.start[0] == line:
                index = line - 1
                prefix = lines[index][:token.start[1]]
                ending = lines[index][token.end[1]:]
                lines[index:index + 1] = [prefix + ending] if prefix.strip() else []
                return "".join(lines)
    elif 0 < line <= len(lines) and lines[line - 1].lstrip().startswith(("#", "//", "--", ";", "/*", "*", "<!--")):
        del lines[line - 1]
    return "".join(lines)
