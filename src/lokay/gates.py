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


def module_name(path):
    parts = path.removeprefix("src/")[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def dead_test_candidates(diff) -> frozenset[str]:
    from lokay.lint import diff_lines

    deleted, modified, roots, tests = set(), set(), set(), {}
    for block in diff.split("diff --git ")[1:]:
        try:
            header = block.split("\n@@ ", 1)[0].splitlines()
            match = re.fullmatch(r'("a/(?:\\.|[^"])*"|a/.*?) ("b/(?:\\.|[^"])*"|b/.*)', header[0])
            if match is None:
                return frozenset()
            before, after = [ast.literal_eval(p) if p.startswith('"') else p for p in match.groups()]
            before, after = before.removeprefix("a/"), after.removeprefix("b/")
            if any(Path(p).is_absolute() or ".." in Path(p).parts for p in (before, after)):
                return frozenset()
            removed = any(line.startswith("deleted file mode ") for line in header)
            renamed = any(line.startswith("rename from ") for line in header)
            added = any(line.startswith("new file mode ") for line in header)
            for path in (before, after):
                if path.endswith(".py") and module_name(path):
                    roots.add(module_name(path).split(".")[0])
            if before.endswith(".py"):
                if removed or renamed:
                    deleted.add(module_name(before))
                elif not added:
                    modified.add(module_name(before))
            if removed and re.fullmatch(r"test_.*\.py|.*_test\.py", Path(before).name):
                source = "\n".join(text for _, _, kind, text in diff_lines("diff --git " + block) if kind == "-")
                tests[before] = source
        except (SyntaxError, ValueError):
            return frozenset()
    candidates = set()
    for path, source in tests.items():
        try:
            imported, possible = False, True
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.ImportFrom):
                    if node.level or any(alias.name == "*" for alias in node.names):
                        possible = False
                        break
                    module = node.module or ""
                    if module.split(".")[0] in roots:
                        imported = True
                        if any(not (module in deleted or module + "." + alias.name in deleted
                                    or module in modified) for alias in node.names):
                            possible = False
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in roots:
                            imported = True
                            if alias.name not in deleted:
                                possible = False
            if imported and possible:
                candidates.add(path)
        except (SyntaxError, ValueError, RecursionError):
            continue
    return frozenset(candidates)


def dead_tests(diff, body, base_paths, head_paths, base_source, head_source) -> frozenset[str]:
    candidates = dead_test_candidates(diff)
    if not candidates:
        return frozenset()
    base_paths, head_paths = set(base_paths), set(head_paths)

    def modules(paths):
        result = {}
        for path in sorted(paths):
            if not path.endswith(".py"):
                continue
            name = module_name(path)
            if name:
                if name in result:
                    raise ValueError("ambiguous module")
                result[name] = path
        return result

    try:
        base_modules, head_modules = modules(base_paths), modules(head_paths)
    except ValueError:
        return frozenset()
    roots = {name.split(".")[0] for name in base_modules}
    tracked = head_paths | {Path(path).name for path in head_paths if Path(path).name != "__init__.py"}
    trees = {}

    def first_party(module):
        return module.split(".")[0] in roots

    def tree(module, head=False):
        key = (module, head)
        if key not in trees:
            path = (head_modules if head else base_modules)[module]
            source = (head_source if head else base_source)(path)
            if source is None:
                raise ValueError("missing source")
            trees[key] = ast.parse(source)
        return trees[key]

    def bindings(node, imports=True):
        result = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [item.name]
            elif isinstance(item, ast.Assign):
                names = [target.id for target in item.targets if isinstance(target, ast.Name)]
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                names = [item.target.id]
            elif imports and isinstance(item, ast.ImportFrom):
                names = [alias.asname or alias.name for alias in item.names]
            elif imports and isinstance(item, ast.Import):
                names = [alias.asname or alias.name.split(".")[0] for alias in item.names]
            else:
                names = []
            for name in names:
                result.setdefault(name, []).append(item)
        return result

    def named(module, symbol=None):
        path = base_modules[module]
        names = [symbol, module + "." + symbol] if symbol else [module, path, Path(path).name]
        return any(re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w./-])", body) for name in names)

    def removed_module(module):
        return (module in base_modules and base_modules[module] not in head_paths
                and named(module))

    def removed_symbol(module, name, depth=0):
        if depth > 5 or module not in base_modules or module not in head_modules:
            return False
        if base_modules[module] not in head_paths or not named(module, name):
            return False
        before = bindings(tree(module)).get(name, [])
        if not before or name in bindings(tree(module, True)):
            return False
        if any(name in bindings(tree(other, True), False) for other in head_modules):
            return False
        for item in before:
            if isinstance(item, ast.Import):
                return False
            if isinstance(item, (ast.Assign, ast.AnnAssign)) and isinstance(item.value, (ast.Name, ast.Attribute)):
                return False
            if isinstance(item, ast.ImportFrom):
                source = item.module or ""
                if item.level:
                    package = module.split(".") if Path(base_modules[module]).name == "__init__.py" else module.split(".")[:-1]
                    if item.level > len(package):
                        return False
                    source = ".".join(package[:len(package) - item.level + 1] + ([source] if source else []))
                if first_party(source):
                    for alias in item.names:
                        if (alias.asname or alias.name) == name and not (
                            removed_module(source + "." + alias.name)
                            or removed_symbol(source, alias.name, depth + 1)
                        ):
                            return False
        return True

    def fixture(node):
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name) and target.id == "fixture":
                return True
            if (isinstance(target, ast.Attribute) and target.attr == "fixture"
                    and isinstance(target.value, ast.Name) and target.value.id == "pytest"):
                return True
        return False

    def proven(path):
        source = base_source(path)
        if source is None or path not in base_paths or path in head_paths:
            return False
        test = ast.parse(source)
        functions = [node for node in ast.walk(test) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        methods = {child for node in ast.walk(test) if isinstance(node, ast.ClassDef) for child in node.body
                   if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
        fixtures = {node.name for node in functions if fixture(node)}
        allowed = fixtures | {"monkeypatch", "tmp_path", "tmp_path_factory", "capsys", "capfd", "caplog", "recwarn"}
        imported = False
        for node in ast.walk(test):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    return False
                module = node.module or ""
                if first_party(module):
                    imported = True
                    for alias in node.names:
                        if alias.name == "*" or not (removed_module(module)
                                or removed_module(module + "." + alias.name)
                                or removed_symbol(module, alias.name)):
                            return False
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if first_party(alias.name):
                        imported = True
                        if not removed_module(alias.name):
                            return False
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(re.search(r"\b" + re.escape(root) + r"\b", node.value) for root in roots):
                    return False
                if any(value in node.value for value in tracked):
                    return False
            elif isinstance(node, ast.Name) and node.id == "__file__":
                return False
            if isinstance(node, ast.Attribute) and node.attr in {"usefixtures", "__import__", "import_module"}:
                return False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"usefixtures", "__import__", "import_module"}:
                return False
        for node in functions:
            positional = node.args.posonlyargs + node.args.args
            args = positional + node.args.kwonlyargs
            args += [arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None]
            if any(arg.arg in {"self", "cls"} and not (
                    node in methods and positional and arg is positional[0]) for arg in args):
                return False
            if node.name.startswith("test") or fixture(node):
                if any(arg.arg not in allowed | {"self", "cls"} for arg in args):
                    return False
        return imported

    dead = set()
    for path in sorted(candidates):
        try:
            if proven(path):
                dead.add(path)
        except (SyntaxError, ValueError, RecursionError, KeyError):
            continue
    return frozenset(dead)


def gate_contract(paths, body) -> str:
    allowed = ", ".join(sorted(path for path in paths if is_test(path) and named_test(path, body)))
    return "\n".join((
        "=== GATE CONTRACT (lokay; overrides the issue where they conflict) ===",
        "Existing test files you may change: " + (allowed or "none"),
        "In those files the number of assertion lines must not drop; replace each outdated assertion with its own equivalent assertion of the current behaviour; never merge, delete or skip assertions.",
        "Do not change, delete, rename or skip any other existing test file, even if the issue asks for it; if the issue's change would require that, implement the rest and report it as a blocker.",
        "Exception: you may delete a whole test file when every project import in it is a module or symbol that you delete and the issue names; lokay proves this deterministically, otherwise the deletion fails the checks.",
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
