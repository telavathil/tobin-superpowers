#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool: ask before installing an unlisted package.

Guards against slopsquatting. When an install command (npm, pnpm, yarn, go get,
pip, uv, poetry) names a package that is not in the nearest manifest, prints a
PreToolUse hookSpecificOutput object with permissionDecision "ask". Never
blocks and never allows: always exits 0, and unparseable input, other commands
and already-listed packages produce no output.
"""

import glob
import json
import os
import re
import shlex
import sys
import tomllib

INSTALLS = {
    ("npm", "install"): "npm", ("npm", "i"): "npm", ("npm", "add"): "npm",
    ("pnpm", "add"): "npm", ("pnpm", "install"): "npm", ("yarn", "add"): "npm",
    ("go", "get"): "go",
    ("pip", "install"): "py", ("pip3", "install"): "py", ("uv", "add"): "py",
    ("uv", "pip", "install"): "py", ("poetry", "add"): "py",
}
MANIFESTS = {"npm": ["package.json"], "go": ["go.mod"], "py": ["pyproject.toml", "requirements*.txt"]}
NPM_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
ARG_FLAGS = {"-r", "-e", "-c", "--requirement", "--editable", "--constraint"}
NPM_NAME = re.compile(r"(@[^/@]+/[^/@]+|[^/@:.][^/@:]*)(@.*)?$")
PY_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
ENV_ASSIGN = re.compile(r"[A-Za-z_]\w*=")
REDIRECT = re.compile(r"\d*[<>]+")
GO_REQUIRE = re.compile(r"^\s*(?:require\s+)?(\S+)\s+v\d", re.M)


def py_norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def py_name(spec):
    m = PY_NAME.match(spec.strip())
    return py_norm(m.group()) if m else None


def package_name(eco, token):
    if eco == "npm":
        m = NPM_NAME.match(token)
        return m.group(1) if m else None
    if eco == "go":
        name = token.split("@")[0]
        return name if re.match(r"[A-Za-z0-9]", name) else None
    if "/" in token or "://" in token:
        return None
    return py_name(token)


def requests(command):
    found = []
    for segment in re.split(r"&&|\|\||[;|&\n()]", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        while tokens and (tokens[0] in ("sudo", "env") or ENV_ASSIGN.match(tokens[0])):
            tokens = tokens[1:]
        if tokens[:3] in (["python", "-m", "pip"], ["python3", "-m", "pip"], ["py", "-m", "pip"]):
            tokens = tokens[2:]
        for prefix, eco in INSTALLS.items():
            if tuple(tokens[:len(prefix)]) == prefix:
                args = iter(tokens[len(prefix):])
                for token in args:
                    if REDIRECT.match(token):
                        if REDIRECT.sub("", token, count=1) == "":
                            next(args, None)
                    elif token in ARG_FLAGS:
                        next(args, None)
                    elif not token.startswith("-"):
                        name = package_name(eco, token)
                        if name:
                            found.append((eco, name))
                break
    return found


def nearest_manifests(eco, cwd):
    directory = os.path.abspath(cwd)
    while True:
        files = sorted(
            f for pattern in MANIFESTS[eco] for f in glob.glob(os.path.join(directory, pattern))
        )
        if files:
            return files
        parent = os.path.dirname(directory)
        if parent == directory:
            return []
        directory = parent


def read_manifest(path):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if name == "package.json":
        data = json.loads(text)
        return {n for s in NPM_SECTIONS for n in data.get(s, {})}
    if name == "go.mod":
        return set(GO_REQUIRE.findall(text))
    if name == "pyproject.toml":
        data = tomllib.loads(text)
        project = data.get("project", {})
        specs = list(project.get("dependencies", []))
        for group in project.get("optional-dependencies", {}).values():
            specs += group
        for group in data.get("dependency-groups", {}).values():
            specs += [s for s in group if isinstance(s, str)]
        poetry = data.get("tool", {}).get("poetry", {})
        names = {py_name(s) for s in specs}
        names |= {py_norm(n) for n in poetry.get("dependencies", {})}
        for group in poetry.get("group", {}).values():
            names |= {py_norm(n) for n in group.get("dependencies", {})}
        return names
    lines = (line.split("#")[0].strip() for line in text.splitlines())
    return {py_name(line) for line in lines if line and not line.startswith("-")}


def is_known(eco, name, known):
    if eco == "go":
        return any(name == m or name.startswith(m + "/") for m in known)
    return name in known


def find_new(command, cwd):
    """Return (manifest paths, package) pairs for requested packages not listed."""
    missing = []
    for eco, name in requests(command):
        files = nearest_manifests(eco, cwd)
        known = set().union(*(read_manifest(f) for f in files)) if files else set()
        if not is_known(eco, name, known):
            missing.append((files, name))
    return missing


def new_packages(command, cwd):
    return [name for _, name in find_new(command, cwd)]


def ask(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.stdout.write("\n")


def main():
    try:
        payload = json.loads(sys.stdin.read())
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or os.getcwd()
        if not isinstance(command, str):
            return 0
    except (ValueError, KeyError, TypeError):
        return 0
    try:
        missing = find_new(command, cwd)
        if missing:
            where = sorted({", ".join(files) or "no manifest found" for files, _ in missing})
            names = ", ".join(name for _, name in missing)
            ask("New package(s) not in %s: %s. Confirm each exists on its registry "
                "(publisher, downloads, repo) before allowing." % ("; ".join(where), names))
    except Exception as e:
        ask("Package check failed: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
