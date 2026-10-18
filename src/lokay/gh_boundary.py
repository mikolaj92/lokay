from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path


BOUNDARY = Path("src/lokay/effects/gh.py")
BIN_NAME = "gh_bin"
LAUNCHES = {"run_process", "subprocess.run", "subprocess.Popen", "subprocess.call",
            "subprocess.check_call", "subprocess.check_output", "subprocess.getoutput",
            "subprocess.getstatusoutput", "os.system", "os.popen"}


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return name(node.value) + "." + node.attr
    return ""


def text(node, values=None, seen=frozenset()):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(text(part.value, values, seen) or "{}" if isinstance(part, ast.FormattedValue)
                       else text(part, values, seen) for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return text(node.left, values, seen) + text(node.right, values, seen)
    if isinstance(node, ast.Name) and values and node.id in values and node.id not in seen:
        return text(values[node.id], values, seen | {node.id})
    return ""


def forbidden(value):
    return bool(re.search(r"--(?:body-file|input)(?:\b|=)|[^\s=]+=@", value))


def shell_errors(source):
    try:
        lexer = shlex.shlex(source, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = source.split()
    for index, token in enumerate(tokens):
        if forbidden(token) or (token == "-F" and index + 1 < len(tokens) and forbidden(tokens[index + 1])):
            yield "file-backed argument bypass"
        if token.rsplit("/", 1)[-1] == "gh":
            following = tokens[index + 1: index + 3]
            if following == ["auth", "token"]:
                continue
            if following and re.fullmatch(r"[a-z][a-z-]*", following[0]):
                yield "shell gh bypass"


def python_errors(tree, boundary):
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    aliases = {}
    values = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or "") + "." + item.name
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value

    def resolved(node):
        raw = name(node)
        head, dot, tail = raw.partition(".")
        return aliases.get(head, head) + dot + tail

    def owner(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    def arguments(node):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [arg for item in node.elts for arg in arguments(item)]
        if isinstance(node, ast.Dict):
            return [arg for item in node.values for arg in arguments(item)]
        return [text(node, values)]

    for node in ast.walk(tree):
        candidates = []
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            candidates = [node.value]
        elif isinstance(node, ast.Call):
            regex = resolved(node.func) in {
                "re.compile", "re.search", "re.match", "re.fullmatch", "re.sub", "re.subn",
                "re.split", "re.findall", "re.finditer"}
            candidates = [*node.args[int(regex):], *(keyword.value for keyword in node.keywords
                                                   if not regex or keyword.arg != "pattern")]
        if any(forbidden(arg) for candidate in candidates for arg in arguments(candidate)):
            yield getattr(node, "lineno", 1), "file-backed argument bypass"
        if not boundary:
            if isinstance(node, (ast.Name, ast.Attribute)) and name(node).split(".")[-1] == BIN_NAME:
                yield node.lineno, "gh_bin outside boundary"
            if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                    item.name.split(".")[-1] == BIN_NAME or item.asname == BIN_NAME for item in node.names):
                yield node.lineno, "gh_bin import outside boundary"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == BIN_NAME:
                yield node.lineno, "gh_bin definition outside boundary"
        if not isinstance(node, ast.Call):
            continue
        called = resolved(node.func)
        if called == "lokay.effects.pi.run_process":
            called = "run_process"
        launch = called in LAUNCHES or called.startswith("os.exec") or called.startswith("os.spawn")
        if not launch:
            continue
        if boundary:
            if owner(node) not in {"_gh", "auth_status"} or called != "run_process":
                yield node.lineno, "process launch outside approved boundary functions"
            elif owner(node) == "_gh":
                expected = ast.parse("[gh_bin(), *args]", mode="eval").body
                if not node.args or ast.dump(node.args[0]) != ast.dump(expected):
                    yield node.lineno, "_gh launch must use only redacted args"
            else:
                expected = ast.parse('[gh_bin(), "auth", "status"]', mode="eval").body
                if not node.args or ast.dump(node.args[0]) != ast.dump(expected):
                    yield node.lineno, "auth_status must launch only auth status"
        if not node.args:
            continue
        argv = node.args[0]
        visited = set()
        while isinstance(argv, ast.Name) and argv.id in values and argv.id not in visited:
            visited.add(argv.id)
            argv = values[argv.id]
        if isinstance(argv, (ast.List, ast.Tuple)) and argv.elts:
            executable = text(argv.elts[0], values)
            if not boundary and executable.rsplit("/", 1)[-1] == "gh":
                yield node.lineno, "direct gh argv outside boundary"
            for arg in argv.elts:
                if forbidden(text(arg, values)):
                    yield node.lineno, "file-backed argument bypass"
        else:
            command = text(argv, values)
            if not boundary:
                for reason in shell_errors(command):
                    yield node.lineno, reason

    if boundary:
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_gh"]
        if len(functions) != 1:
            yield 1, "expected one _gh boundary"
            return
        function = functions[0]
        canonical = ast.parse('''args = [redact_text(arg, env) for arg in args]
for index, arg in enumerate(args):
    if re.search(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}", arg):
        subcommand = " ".join(part if re.fullmatch(r"[a-z][a-z-]*", part) else "?" for part in args[:2])
        message = f"gh post blocked: GitHub token pattern survived redaction (arg {index}, {subcommand})"
        logging.getLogger(__name__).error(message)
        raise SafetyError(message)
index = 0
while index < len(args):
    arg = args[index]
    if arg in ("--body", "--title") and index + 1 < len(args):
        index += 1
        args[index] = fit_body(args[index]) if arg == "--body" else args[index][:256]
    elif arg.startswith("--body="):
        args[index] = "--body=" + fit_body(arg[len("--body="):])
    elif arg.startswith("--title="):
        args[index] = "--title=" + arg[len("--title="):][:256]
    index += 1
validate_argv(["gh", *args])
''').body
        if [ast.dump(node) for node in function.body[:len(canonical)]] != [ast.dump(node) for node in canonical]:
            yield function.lineno, "_gh must redact every arg with env and block surviving GitHub tokens before trimming and validation"
        for statement in function.body[len(canonical):]:
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == "args":
                    yield node.lineno, "redacted args reassigned after validation"
                if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)) and name(node.value) == "args":
                    yield node.lineno, "redacted args changed after validation"
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and name(node.func.value) == "args":
                    yield node.lineno, "redacted args mutated after validation"
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                   and node.module == "lokay.redact" and any(item.name == "redact_text" and item.asname is None for item in node.names)]
        if not imports or any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == "redact_text"
                              for node in ast.walk(tree)):
            yield function.lineno, "_gh must use lokay.redact.redact_text"


def scan(path, root):
    source = path.read_text()
    relative = path.relative_to(root)
    if path.suffix == ".py":
        parts = [(source, 0)]
        shell = []
    else:
        parts = []
        shell = []
        lines = source.splitlines(keepends=True)
        index = 0
        while index < len(lines):
            match = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", lines[index])
            if match:
                start = index + 1
                index = start
                while index < len(lines) and lines[index].strip() != match[1]:
                    index += 1
                body = "".join(lines[start:index])
                if "python" in lines[start - 1] or match[1].upper().startswith("PY"):
                    parts.append((body, start))
                else:
                    shell.extend((number + 1, lines[number]) for number in range(start, index))
            else:
                shell.append((index + 1, lines[index]))
            index += 1
    for number, line in shell:
        if not line.lstrip().startswith("#"):
            for reason in shell_errors(line):
                yield number, reason
    for body, offset in parts:
        try:
            tree = ast.parse(body)
        except SyntaxError as exc:
            yield offset + (exc.lineno or 1), "cannot parse Python boundary source"
            continue
        for number, reason in python_errors(tree, relative == BOUNDARY):
            yield offset + number, reason


def main():
    root = Path.cwd()
    paths = sorted({*root.glob("src/**/*.py"), *(path for path in (root / "scripts").rglob("*") if path.is_file())})
    errors = sorted({(str(path.relative_to(root)), number, reason)
                     for path in paths for number, reason in scan(path, root)})
    for path, number, reason in errors:
        print(f"{path}:{number}: {reason} -> call lokay.effects.gh")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
