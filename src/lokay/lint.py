import ast
import io
import re
import tokenize
from pathlib import Path

from lokay.effects.git import git_try
from lokay.scope import is_test


def git_output(cwd: Path, args: list[str]) -> str:
    code, out, err = git_try(cwd, *args)
    if code:
        raise ValueError(err.strip() or out.strip())
    return out


def diff_lines(diff: str):
    path = ""
    line_number = 0
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = ""
            in_hunk = False
        elif not in_hunk and line.startswith(("--- ", "+++ ")) and line != "+++ /dev/null":
            path = line[4:].split("\t", 1)[0]
            if path.startswith('"'):
                path = ast.literal_eval(path)
            if path.startswith("a/" if line.startswith("--- ") else "b/"):
                path = path[2:]
            if Path(path).is_absolute() or ".." in Path(path).parts:
                path = ""
        elif line.startswith("@@ "):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            in_hunk = match is not None
            if match:
                line_number = int(match[1])
        elif in_hunk and line[:1] in {"+", "-", " "}:
            if path:
                yield path, line_number, line[0], line[1:]
            if line[0] != "-":
                line_number += 1


def unit_test_files(diff: str) -> list[str]:
    paths = []
    changes = {}
    added_lines = {}
    for path, _, kind, text in diff_lines(diff):
        if kind == "+":
            added_lines.setdefault(path, []).append(text)
        if text.strip() and kind in {"+", "-"}:
            changes[path] = changes.get(path, 0) + (1 if kind == "+" else -1)
    paths.extend(path for path, net in changes.items() if net > 0)
    for block in diff.split("diff --git ")[1:]:
        lines = block.splitlines()
        if not any(line.startswith("new file mode ") for line in lines):
            continue
        path = lines[0].split(" b/", 1)[-1]
        for line in lines[1:]:
            if line.startswith("+++ "):
                path = line[4:].split("\t", 1)[0]
                if path.startswith('"'):
                    path = ast.literal_eval(path)
                path = path.removeprefix("b/")
                break
        paths.append(path)
    return sorted({path for path in paths if is_test(path, added_lines.get(path, ()))
                   and not Path(path).is_absolute() and ".." not in Path(path).parts
                   and not any(Path(path).parts[i:i + 2] == ("fixtures", "replay")
                               for i in range(len(Path(path).parts) - 1))})


def lint_diff(diff: str, head: str, cwd: Path, lokay_rules: bool) -> list[str]:
    errors = []
    if lokay_rules:
        for block in diff.split("diff --git ")[1:]:
            lines = block.splitlines()
            if any(line.startswith("new file mode ") for line in lines):
                continue
            paths = lines[0].split(" b/", 1)
            paths[0] = paths[0].removeprefix("a/")
            for path in paths:
                if path.startswith("fixtures/ticks/"):
                    errors.append(f"{path}: recorded tick fixture changed -> never edit recordings; adjust replay matching in src/lokay/effects/replay.py")
    added = {}
    for path, number, kind, text in diff_lines(diff):
        if kind != "+" or not path.endswith(".py"):
            continue
        added.setdefault(path, set()).add(number)
        if lokay_rules and path != "src/lokay/lint.py":
            if re.search(r"\badd\s+(?:-A\b|--all\b|\.(?:\s|$))|['\"]add['\"]\s*,\s*['\"](?:-A|--all|\.)['\"]", text):
                errors.append(f"{path}:{number}: staging all files -> use lokay.effects.git.commit_paths(changed)")
            if path.startswith("src/lokay/") and not path.startswith("src/lokay/effects/") and re.search(
                r"\bimport\s+subprocess\b|\bfrom\s+subprocess\b|\bsubprocess\.", text
            ):
                errors.append(f"{path}:{number}: process execution outside effects -> use lokay.effects")
        if lokay_rules and re.search(r"\.get\(['\"](?:plik|zmiana|pytanie|linia_od|linia_do|note)['\"]|\[['\"](?:plik|zmiana|pytanie|linia_od|linia_do|note)['\"]\]", text):
            errors.append(f"{path}:{number}: raw finding dict access -> use lokay.types.Finding/Note fields")
    for path, numbers in added.items():
        source = git_output(cwd, ["show", f"{head}:{path}"])
        try:
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type != tokenize.COMMENT or token.start[0] not in numbers:
                    continue
                if token.string.startswith(("#!", "# type:", "# noqa")) or re.match(
                    r"#.*?coding[:=]\s*[-\w.]+", token.string
                ):
                    continue
                errors.append(f"{path}:{token.start[0]}: new comment -> delete it; name the function instead")
            tree = ast.parse(source)
        except (SyntaxError, tokenize.TokenError, IndentationError) as exc:
            errors.append(f"{path}: invalid Python -> fix syntax: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    if numbers.intersection(range(first.lineno, (first.end_lineno or first.lineno) + 1)):
                        errors.append(f"{path}:{first.lineno}: docstring -> delete it")
            if lokay_rules and isinstance(node, ast.List) and node.elts and path not in {"src/lokay/effects/git.py", "src/lokay/effects/gh.py"}:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value in ("git", "gh"):
                    if numbers.intersection(range(node.lineno, (node.end_lineno or node.lineno) + 1)):
                        errors.append(f"{path}:{node.lineno}: git/gh outside effects/git.py or effects/gh.py -> call lokay.effects.git / lokay.effects.gh")
    hint = ("add a replay fixture under fixtures/replay and run uv run lokay replay" if lokay_rules else
            "keep the test change inside existing test functions with no net added lines, or remove the added test code")
    errors.extend(f"{path}: new unit test -> {hint}" for path in unit_test_files(diff))
    return sorted(set(errors))


def lint(base: str, head: str, cwd: Path) -> list[str]:
    diff = git_output(cwd, ["diff", "--no-ext-diff", "--no-textconv", "--no-renames", "-U0", base, head, "--"])
    return lint_diff(diff, head, cwd, lokay_rules=True)
