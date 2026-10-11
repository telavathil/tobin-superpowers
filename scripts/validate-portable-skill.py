#!/usr/bin/env python3
"""Static checks for a portable skill candidate (promote-skill workflow).

Usage: python3 scripts/validate-portable-skill.py PATH [--deny-terms FILE] [--json]
       python3 scripts/validate-portable-skill.py PATH --digest

PATH is either a staging folder (manifest.json, REVIEW.md, skill/) or a bare
skill folder containing SKILL.md (used to inspect a source skill read-only, or
an imported copy). Checks: structure and frontmatter, name rules, listed and
referenced files (including path escapes and symlinks), Python dependencies,
manifest schema, REVIEW.md sections and approval consistency, and an advisory
portability scan (machine paths, internal URLs, credential-like strings,
organisation config, confidentiality markers, optional deny-list terms).

It reads files only: it never executes candidate content, never runs the
manifest's validation commands, never modifies anything, and never prints a
matched credential or deny-list term. Passing it does not prove a candidate is
free of confidential material, and it never records approval.

--digest prints the SHA-256 digest of the skill files that approval binds to.

Exit codes: 0 no errors (warnings allowed), 1 errors, 2 invalid invocation or
unreadable input.
"""

import argparse
import ast
import hashlib
import ipaddress
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MANIFEST_KEYS = ("schema_version", "name", "description", "mode", "requires", "files",
                 "validation_commands", "status", "approval")
REQUIRES_KEYS = ("runtime", "tools", "dependencies")
APPROVAL_KEYS = ("approved_by_user", "digest", "transfer_authorized", "publication_authorized")
MODES = ("source", "personal")
STATUSES = ("draft", "needs-changes", "approved", "blocked")
REVIEW_STATUS = {"draft": "pending", "needs-changes": "needs-changes",
                 "approved": "approved", "blocked": "blocked"}
REVIEW_SECTIONS = ("Purpose", "Inventory", "Preserved", "Portability Changes", "Exclusions",
                   "Remaining Dependencies", "Validation Results", "Risks", "Approval")
SKILL_LAYOUT = {"SKILL.md": "file", "references": "dir", "scripts": "dir", "tests": "dir"}
IGNORED_NAMES = {"__pycache__", ".DS_Store"}
MAX_SCAN_BYTES = 1_000_000

# Official superpowers skills and this plugin's own skills: a promoted skill
# may never take one of these names.
UPSTREAM_SKILLS = {
    "brainstorming", "diagnosing-superpowers", "dispatching-parallel-agents",
    "executing-plans", "finishing-a-development-branch", "receiving-code-review",
    "requesting-code-review", "subagent-driven-development", "systematic-debugging",
    "test-driven-development", "using-git-worktrees", "using-superpowers",
    "verification-before-completion", "writing-plans", "writing-skills",
}
EXTENSION_SKILLS = {"hybrid-planning", "html-companion", "promote-skill", "shared"}
RESERVED_NAMES = UPSTREAM_SKILLS | EXTENSION_SKILLS

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

REL_REF_RE = re.compile(r"(?<![\w./$}-])((?:references|scripts|tests)/\w[\w./-]*)")
PLUGIN_REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/skills/([\w-]+)/(\w[\w./-]*)")
MD_LINK_RE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
SCHEME_RE = re.compile(r"^[A-Za-z][\w+.-]*:")

ABS_PATH_RE = re.compile(
    r"(?<![\w.:/\\])(?:/(?:Users|home|Volumes)/[\w.-]+|/mnt/[a-z]/Users/[\w.-]+"
    r"|[A-Za-z]:\\(?:Users\\[\w.-]+|[\w.-]+\\)|\\\\[\w.-]+\\[\w$.-]+)")
URL_RE = re.compile(r"\b(?:https?|ssh|git|ftp|wss?)://[^\s<>\"'`)\]]+", re.I)
SCP_RE = re.compile(r"\b[\w.-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*):[\w~]")
INTERNAL_LABELS = {"internal", "corp", "intranet", "intra", "local", "lan", "private", "localdomain"}

CREDENTIAL_PATTERNS = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("GitHub token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("private key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("API key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("credential in URL", re.compile(r"://[^/\s:@]+:[^/\s:@]+@")),
)
ASSIGNMENT_RE = re.compile(
    r"(?i)\b[\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|access[_-]?key)\b[\"']?\s*[:=]\s*"
    r"(?:([\"'])([^\"'\s]{8,})\1|([A-Za-z0-9_+/=-]{16,}))")
PLACEHOLDER_HINTS = ("example", "changeme", "placeholder", "your", "xxxx", "dummy", "redacted",
                     "replace", "sample", "fake", "****", "...", "test")
CONFIG_RE = re.compile(
    r"(?i)(\.npmrc|\.pypirc|pip\.conf|\.netrc|\.aws/(?:credentials|config)|\.kube/config"
    r"|\.docker/config\.json|\bartifactory\b|\bjfrog\b|\bnexus repository\b|\bregistry\s*="
    r"|\bindex-url\s*=|\bAWS_PROFILE\b|\bVAULT_ADDR\b)")
MARKER_RE = re.compile(
    r"(?i:\binternal use only\b|\bproprietary and confidential\b|\bdo not (?:distribute|share)\b"
    r"|\bconfidential\s*[-:\u2013]\s*internal\b|\b(?:company|strictly|highly)\s+confidential\b)"
    r"|\b[A-Z][\w&.]*(?: [A-Z][\w&.]*)* confidential\b")


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: Optional[str]
    line: Optional[int]
    message: str
    suggestion: str

    def to_dict(self):
        return asdict(self)


class InputError(ValueError):
    """The path to validate does not exist or cannot be read."""


def valid_name(name):
    return isinstance(name, str) and 0 < len(name) <= 64 and bool(NAME_RE.match(name))


def errors(findings):
    return [f for f in findings if f.severity == "error"]


def read_text(path):
    with open(path, "rb") as handle:
        data = handle.read(MAX_SCAN_BYTES + 1)
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def ignored(name):
    return name in IGNORED_NAMES or name.endswith(".pyc")


def walk_skill(skill_dir):
    """Return (regular files as posix relpaths, symlink relpaths); never follows links."""
    files, links = [], []
    for dirpath, dirs, names in os.walk(skill_dir):
        for name in list(dirs):
            if ignored(name) or os.path.islink(os.path.join(dirpath, name)):
                dirs.remove(name)
                if not ignored(name):
                    links.append(os.path.relpath(os.path.join(dirpath, name), skill_dir))
        for name in names:
            if ignored(name):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, skill_dir)
            (links if os.path.islink(full) else files).append(rel)
    norm = lambda rel: rel.replace(os.sep, "/")  # noqa: E731
    return sorted(map(norm, files)), sorted(map(norm, links))


def compute_digest(skill_dir):
    """SHA-256 over the relative path and content of every regular skill file."""
    files, _ = walk_skill(skill_dir)
    outer = hashlib.sha256()
    for rel in files:
        with open(os.path.join(skill_dir, *rel.split("/")), "rb") as handle:
            inner = hashlib.sha256(handle.read()).hexdigest()
        outer.update(rel.encode("utf-8") + b"\0" + inner.encode("ascii") + b"\n")
    return "sha256:" + outer.hexdigest()


def load_deny_terms(path):
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        raise InputError("cannot read deny-terms file: %s" % exc)
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def unsafe_relpath(entry):
    """True if a manifest entry is absolute or could escape the skill folder."""
    if not isinstance(entry, str) or not entry or "\\" in entry or "\0" in entry:
        return True
    if entry.startswith("/") or re.match(r"^[A-Za-z]:", entry):
        return True
    return any(part in ("..", "") for part in entry.split("/"))


def parse_frontmatter(text):
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None
    lines = text.splitlines()
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        match = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip().strip("\"'")
    return None


# --- portability scan ----------------------------------------------------

def is_internal_host(host):
    host = (host or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        labels = host.split(".")
        return len(labels) == 1 or any(label in INTERNAL_LABELS for label in labels)
    return (ip.is_private or ip.is_link_local) and not ip.is_loopback


def internal_urls(line):
    hits = []
    for match in URL_RE.finditer(line):
        try:
            host = urlsplit(match.group(0).rstrip(".,;:")).hostname
        except ValueError:
            continue
        if is_internal_host(host):
            hits.append(host)
    hits.extend(m.group(1) for m in SCP_RE.finditer(line) if is_internal_host(m.group(1)))
    return hits


def looks_like_placeholder(value):
    low = value.lower()
    return (value[0] in "<${%" or any(h in low for h in PLACEHOLDER_HINTS)
            or len(set(value)) <= 2)


def credential_kinds(line):
    kinds = [label for label, pattern in CREDENTIAL_PATTERNS if pattern.search(line)]
    for match in ASSIGNMENT_RE.finditer(line):
        value = match.group(2) or match.group(3)
        if match.group(3) and not (re.search(r"\d", value) and re.search(r"[A-Za-z]", value)):
            continue
        if not looks_like_placeholder(value):
            kinds.append("secret assignment")
    return kinds


def deny_hits(line, deny_terms):
    low = line.lower()
    return [i for i, term in enumerate(deny_terms, 1) if term.lower() in low]


def scan_text(rel, text, deny_terms):
    """Advisory portability findings for one text file. Never echoes secrets."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in ABS_PATH_RE.finditer(line):
            found.append(Finding("absolute-path", "warning", rel, number,
                                 "machine-specific absolute path %s" % match.group(0),
                                 "Use a path relative to the skill, a placeholder such as <project>, or ask the user at run time."))
        for host in internal_urls(line):
            found.append(Finding("internal-url", "warning", rel, number,
                                 "private or internal host %s" % host,
                                 "Remove the link or replace it with public documentation or a bundled reference."))
        for kind in credential_kinds(line):
            found.append(Finding("credential", "error", rel, number,
                                 "possible %s (value redacted)" % kind,
                                 "Delete the value and rotate it if it was real; read credentials from the environment at run time."))
        for match in CONFIG_RE.finditer(line):
            found.append(Finding("company-config", "warning", rel, number,
                                 "relies on organisation configuration (%s)" % match.group(1),
                                 "Use public defaults or document the setting as optional user configuration."))
        if MARKER_RE.search(line):
            found.append(Finding("confidential-marker", "warning", rel, number,
                                 "confidentiality or distribution notice",
                                 "Stop: confirm the material may leave its owner, or rebuild it clean-room from generic requirements."))
        for index in deny_hits(line, deny_terms):
            found.append(Finding("deny-term", "error", rel, number,
                                 "matches deny-list term #%d (term not shown)" % index,
                                 "Remove or generalize the wording."))
    return found


# --- skill checks --------------------------------------------------------

def check_skill(skill_dir, manifest, deny_terms, prefix):
    """Findings for a skill folder; manifest may be None (bare skill mode)."""
    found = []
    shown = lambda rel: prefix + rel  # noqa: E731
    if os.path.islink(skill_dir):
        return [Finding("symlink", "error", shown(""), None, "skill folder is a symbolic link",
                        "Replace it with a real folder; links can point outside the candidate.")]
    if not os.path.isdir(skill_dir):
        return [Finding("structure", "error", shown(""), None, "skill folder is missing",
                        "Create skill/ with SKILL.md.")]
    files, links = walk_skill(skill_dir)
    for rel in links:
        found.append(Finding("symlink", "error", shown(rel), None, "symbolic link inside the skill",
                             "Replace the link with the file it should contain, or remove it."))
    for entry in sorted(os.listdir(skill_dir)):
        if ignored(entry):
            continue
        kind = SKILL_LAYOUT.get(entry)
        full = os.path.join(skill_dir, entry)
        actual = "dir" if os.path.isdir(full) else "file"
        if kind is None or (kind != actual and not os.path.islink(full)):
            found.append(Finding("layout", "error", shown(entry), None,
                                 "unexpected top-level entry (allowed: SKILL.md, references/, scripts/, tests/)",
                                 "Move it under references/, scripts/ or tests/, or exclude it."))

    skill_md = os.path.join(skill_dir, "SKILL.md")
    name = None
    if "SKILL.md" not in files:
        found.append(Finding("structure", "error", shown("SKILL.md"), None, "SKILL.md is missing",
                             "Add SKILL.md with name and description frontmatter."))
    else:
        text = read_text(skill_md) or ""
        fields = parse_frontmatter(text)
        if fields is None:
            found.append(Finding("frontmatter", "error", shown("SKILL.md"), 1, "missing or unterminated YAML frontmatter",
                                 "Start the file with ---, name:, description:, ---."))
        else:
            for key in ("name", "description"):
                if not fields.get(key):
                    found.append(Finding("frontmatter", "error", shown("SKILL.md"), 1, "frontmatter has no %s" % key,
                                         "Add a %s: line." % key))
            if len(fields.get("description", "")) > 1024:
                found.append(Finding("frontmatter", "warning", shown("SKILL.md"), 1, "description longer than 1024 characters",
                                     "Shorten it; it is loaded into every session's skill list."))
            if "allowed-tools" in fields:
                found.append(Finding("frontmatter", "warning", shown("SKILL.md"), 1,
                                     "allowed-tools needs a load permission that headless runs deny",
                                     "Remove allowed-tools unless the skill truly needs it."))
            name = fields.get("name")
            if name:
                found.extend(check_name(name, shown("SKILL.md")))
        if manifest is not None and name and isinstance(manifest.get("name"), str) and manifest["name"] != name:
            found.append(Finding("name", "error", shown("SKILL.md"), 1,
                                 "frontmatter name does not match manifest name",
                                 "Use the same name in both."))

    found.extend(check_references(skill_dir, files, name, shown))
    found.extend(check_dependencies(skill_dir, files, manifest, shown))
    for rel in files:
        full = os.path.join(skill_dir, *rel.split("/"))
        if os.path.getsize(full) > MAX_SCAN_BYTES:
            found.append(Finding("size", "warning", shown(rel), None, "file over 1 MB was not scanned",
                                 "Keep skill files small and text-only."))
            continue
        text = read_text(full)
        if text is None:
            found.append(Finding("binary", "warning", shown(rel), None, "binary file was not scanned",
                                 "Review it by hand or exclude it."))
            continue
        found.extend(scan_text(shown(rel), text, deny_terms))

    if manifest is not None and isinstance(manifest.get("files"), list):
        listed = manifest["files"]
        for entry in listed:
            if unsafe_relpath(entry):
                found.append(Finding("path-escape", "error", "manifest.json", None,
                                     "files entry is absolute or leaves the skill folder",
                                     "List paths relative to skill/ without '..'."))
            elif entry not in files:
                found.append(Finding("files", "error", "manifest.json", None,
                                     "listed file is missing: %s" % entry, "Add the file or remove the entry."))
        for rel in files:
            if rel not in listed:
                found.append(Finding("files", "error", shown(rel), None, "file is not listed in manifest files",
                                     "List it (it will be imported) or delete it from the candidate."))
    return found


def check_name(name, where):
    if not valid_name(name):
        return [Finding("name", "error", where, None,
                        "invalid skill name (lowercase letters, digits and single hyphens, at most 64)",
                        "Use a name like diagram-as-code.")]
    if name in RESERVED_NAMES:
        return [Finding("name", "error", where, None,
                        "name is reserved by official superpowers or this plugin: %s" % name,
                        "Choose a distinct name; promoted skills never replace those skills.")]
    return []


def check_references(skill_dir, files, name, shown):
    found = []
    root = os.path.realpath(skill_dir)
    for rel in files:
        if not rel.endswith(".md"):
            continue
        text = read_text(os.path.join(skill_dir, *rel.split("/"))) or ""
        base = os.path.dirname(rel)
        for number, line in enumerate(text.splitlines(), 1):
            refs = [(m.group(1), "") for m in REL_REF_RE.finditer(line)]
            refs += [(m.group(2), "") for m in PLUGIN_REF_RE.finditer(line) if m.group(1) == name]
            refs += [(m.group(1), base) for m in MD_LINK_RE.finditer(line)
                     if not SCHEME_RE.match(m.group(1)) and not m.group(1).startswith(("#", "/", "~"))]
            for ref, start in refs:
                ref = ref.split("#", 1)[0].rstrip(".,;:")
                if not ref:
                    continue
                target = os.path.normpath(os.path.join(root, start, ref))
                if os.path.relpath(target, root).split(os.sep)[0] == "..":
                    found.append(Finding("path-escape", "error", shown(rel), number,
                                         "reference leaves the skill folder: %s" % ref,
                                         "Bundle the file under references/ or remove the reference."))
                elif not os.path.exists(target):
                    found.append(Finding("reference", "error", shown(rel), number,
                                         "referenced file does not exist: %s" % ref,
                                         "Add the file to the candidate or fix the reference."))
    return found


def python_imports(text):
    tree = ast.parse(text)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules.add(node.module.split(".")[0])
    return modules


def check_dependencies(skill_dir, files, manifest, shown):
    found = []
    local = {os.path.splitext(os.path.basename(rel))[0] for rel in files if rel.endswith(".py")}
    local |= {rel.split("/")[-2] for rel in files if rel.endswith("/__init__.py")}
    declared = " ".join(manifest.get("requires", {}).get("dependencies", []) or []
                        if manifest and isinstance(manifest.get("requires"), dict) else []).lower()
    stdlib = set(sys.stdlib_module_names)
    for rel in files:
        if not rel.endswith(".py"):
            continue
        try:
            modules = python_imports(read_text(os.path.join(skill_dir, *rel.split("/"))) or "")
        except SyntaxError as exc:
            found.append(Finding("dependency", "warning", shown(rel), exc.lineno,
                                 "could not parse Python to check imports", "Fix the syntax error."))
            continue
        for module in sorted(modules - stdlib - local - {"__future__"}):
            if manifest is None:
                found.append(Finding("dependency", "warning", shown(rel), None,
                                     "non-standard-library import %s" % module,
                                     "Declare it in the manifest's requires.dependencies."))
            elif re.search(r"\b%s\b" % re.escape(module.lower()), declared):
                found.append(Finding("unsupported-dependency", "warning", shown(rel), None,
                                     "declared non-standard-library dependency %s" % module,
                                     "This plugin's own scripts are stdlib-only; keep it optional or document installation."))
            else:
                found.append(Finding("dependency", "error", shown(rel), None,
                                     "undeclared non-standard-library import %s" % module,
                                     "Declare it in requires.dependencies or remove it."))
    return found


# --- staging checks ------------------------------------------------------

def check_manifest(manifest):
    found = []

    def bad(message, suggestion="Fix manifest.json to match schema_version 1."):
        found.append(Finding("manifest", "error", "manifest.json", None, message, suggestion))

    if not isinstance(manifest, dict):
        bad("manifest is not a JSON object")
        return found
    for key in MANIFEST_KEYS:
        if key not in manifest:
            bad("missing key: %s" % key)
    for key in sorted(set(manifest) - set(MANIFEST_KEYS)):
        found.append(Finding("manifest", "warning", "manifest.json", None, "unknown key: %s" % key,
                             "Remove it; only schema keys are kept."))
    version = manifest.get("schema_version")
    if "schema_version" in manifest and (type(version) is not int or version != SCHEMA_VERSION):
        bad("schema_version must be %d" % SCHEMA_VERSION)
    if "name" in manifest:
        found.extend(check_name(manifest["name"], "manifest.json"))
    if "description" in manifest and not (isinstance(manifest["description"], str) and manifest["description"].strip()):
        bad("description must be a non-empty string")
    if "mode" in manifest and manifest["mode"] not in MODES:
        bad("mode must be one of %s" % ", ".join(MODES))
    if "status" in manifest and manifest["status"] not in STATUSES:
        bad("status must be one of %s" % ", ".join(STATUSES))
    requires = manifest.get("requires")
    if "requires" in manifest:
        if not isinstance(requires, dict) or any(
                not isinstance(requires.get(k), list) or not all(isinstance(v, str) for v in requires.get(k))
                for k in REQUIRES_KEYS):
            bad("requires must have runtime, tools and dependencies lists of strings")
    files = manifest.get("files")
    if "files" in manifest:
        if not isinstance(files, list) or not all(isinstance(v, str) for v in files):
            bad("files must be a list of strings")
        elif "SKILL.md" not in files or len(set(files)) != len(files):
            bad("files must include SKILL.md once and list each file once")
    commands = manifest.get("validation_commands")
    if "validation_commands" in manifest and (
            not isinstance(commands, list) or not all(isinstance(v, str) for v in commands)):
        bad("validation_commands must be a list of strings")
    approval = manifest.get("approval")
    if "approval" in manifest:
        if not isinstance(approval, dict) or set(approval) != set(APPROVAL_KEYS):
            bad("approval must have exactly: %s" % ", ".join(APPROVAL_KEYS))
        else:
            for key in ("approved_by_user", "transfer_authorized", "publication_authorized"):
                if not isinstance(approval[key], bool):
                    bad("approval.%s must be true or false" % key)
            digest = approval["digest"]
            if digest is not None and not (isinstance(digest, str) and DIGEST_RE.match(digest)):
                bad("approval.digest must be null or sha256:<64 hex>")
    return found


def check_manifest_privacy(text, deny_terms):
    found = []
    for f in scan_text("manifest.json", text, deny_terms):
        if f.rule in ("absolute-path", "internal-url", "credential", "deny-term"):
            message = f.message if f.rule in ("credential", "deny-term") else f.rule.replace("-", " ")
            found.append(Finding("manifest-private", "error", "manifest.json", f.line,
                                 "manifest must not contain private details (%s)" % message,
                                 "Keep source paths, employer names, internal URLs and credentials out of the manifest."))
    return found


def review_fields(text):
    sections = {m.group(1).strip().lower() for m in re.finditer(r"^##\s+(.+?)\s*#*\s*$", text, re.M)}
    _, _, approval = text.partition("## Approval")

    def field(label):
        match = re.search(r"^%s:\s*(\S+)" % label, approval, re.M | re.I)
        return match.group(1).strip().lower().rstrip(".") if match else None

    return sections, field("Status"), field("Transfer authorized"), field("Publication authorized")


def check_review(text, manifest):
    found = []
    sections, status, transfer, publication = review_fields(text)
    for section in REVIEW_SECTIONS:
        if section.lower() not in sections:
            found.append(Finding("review", "error", "REVIEW.md", None, "missing section: ## %s" % section,
                                 "Add the section; see the promote-skill REVIEW.md template."))
    for label, value, allowed in (("Status", status, set(REVIEW_STATUS.values())),
                                  ("Transfer authorized", transfer, {"yes", "no"}),
                                  ("Publication authorized", publication, {"yes", "no"})):
        if value not in allowed:
            found.append(Finding("review", "error", "REVIEW.md", None,
                                 "Approval section needs '%s: %s'" % (label, "|".join(sorted(allowed))),
                                 "Record the user's decision in the Approval section."))
    if not isinstance(manifest, dict):
        return found
    expected = REVIEW_STATUS.get(manifest.get("status"))
    if status in REVIEW_STATUS.values() and expected and status != expected:
        found.append(Finding("review-status", "error", "REVIEW.md", None,
                             "REVIEW status %s does not match manifest status %s" % (status, manifest.get("status")),
                             "Update both together; draft corresponds to pending."))
    approval = manifest.get("approval") if isinstance(manifest.get("approval"), dict) else {}
    for label, value, key in (("Transfer authorized", transfer, "transfer_authorized"),
                              ("Publication authorized", publication, "publication_authorized")):
        if value in ("yes", "no") and isinstance(approval.get(key), bool) and (value == "yes") != approval[key]:
            found.append(Finding("review-status", "error", "REVIEW.md", None,
                                 "'%s' does not match manifest approval.%s" % (label, key),
                                 "Record the same decision in both files."))
    return found


def check_approval(manifest, skill_dir):
    found = []
    approval = manifest.get("approval")
    if not isinstance(approval, dict):
        return found
    status = manifest.get("status")

    def bad(message, suggestion):
        found.append(Finding("approval", "error", "manifest.json", None, message, suggestion))

    if status == "approved":
        if approval.get("approved_by_user") is not True:
            bad("status is approved but approval.approved_by_user is not true",
                "Only the user approves; record it after their explicit approval.")
        digest = approval.get("digest")
        if not digest:
            bad("approved candidate has no digest",
                "Record the --digest output at the moment the user approves.")
        elif os.path.isdir(skill_dir) and not os.path.islink(skill_dir) and digest != compute_digest(skill_dir):
            found.append(Finding("digest-mismatch", "error", "manifest.json", None,
                                 "skill files changed after approval",
                                 "Re-run validation and review, then ask the user to approve again."))
    elif approval.get("approved_by_user") is True:
        bad("approval.approved_by_user is true but status is %s" % status,
            "Set status to approved only with the user's explicit approval, otherwise clear the flag.")
    if approval.get("publication_authorized") is True and approval.get("transfer_authorized") is not True:
        bad("publication authorized without transfer authorization",
            "Ask for transfer permission first; publication is a separate, later decision.")
    return found


def validate_path(path, deny_terms=()):
    """Validate a staging folder or a bare skill folder."""
    deny_terms = list(deny_terms or ())
    if not os.path.isdir(path):
        raise InputError("not a folder: %s" % path)
    if os.path.isfile(os.path.join(path, "SKILL.md")) and not os.path.exists(os.path.join(path, "manifest.json")):
        return sort_findings(check_skill(path, None, deny_terms, ""))

    found = []
    skill_dir = os.path.join(path, "skill")
    manifest_path = os.path.join(path, "manifest.json")
    review_path = os.path.join(path, "REVIEW.md")
    manifest = None
    for label, full in (("manifest.json", manifest_path), ("REVIEW.md", review_path)):
        if os.path.islink(full):
            found.append(Finding("symlink", "error", label, None, "%s is a symbolic link" % label,
                                 "Replace it with a regular file."))
        elif not os.path.isfile(full):
            found.append(Finding("structure", "error", label, None, "%s is missing" % label,
                                 "Create it; see the promote-skill templates."))
    if os.path.isfile(manifest_path) and not os.path.islink(manifest_path):
        text = read_text(manifest_path) or ""
        try:
            manifest = json.loads(text)
        except ValueError as exc:
            found.append(Finding("manifest", "error", "manifest.json", getattr(exc, "lineno", None),
                                 "invalid JSON", "Fix the JSON syntax."))
        else:
            found.extend(check_manifest(manifest))
        found.extend(check_manifest_privacy(text, deny_terms))
    if not isinstance(manifest, dict):
        manifest = None
    found.extend(check_skill(skill_dir, manifest or {}, deny_terms, "skill/"))
    if os.path.isfile(review_path) and not os.path.islink(review_path):
        text = read_text(review_path) or ""
        found.extend(check_review(text, manifest))
        found.extend(f for f in scan_text("REVIEW.md", text, deny_terms))
    if manifest is not None:
        found.extend(check_approval(manifest, skill_dir))
    return sort_findings(found)


def sort_findings(findings):
    unique = list(dict.fromkeys(findings))
    return sorted(unique, key=lambda f: (SEVERITY_ORDER[f.severity], f.path or "", f.line or 0, f.rule))


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def format_text(display_path, findings):
    lines = []
    for f in findings:
        where = f.path or display_path
        if f.line:
            where = "%s:%d" % (where, f.line)
        lines.append("%s: %s [%s] %s\n    fix: %s" % (where, f.severity, f.rule, f.message, f.suggestion))
    counts = [sum(1 for f in findings if f.severity == s) for s in ("error", "warning")]
    lines.append("Summary: %s, %s - %s" % (plural(counts[0], "error"), plural(counts[1], "warning"), display_path))
    lines.append("Advisory: passing does not prove the candidate is free of confidential material "
                 "or that you may reuse it.")
    return "\n".join(lines)


def tolerate_console_encoding():
    """Keep printing on consoles that cannot encode every character."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")


def skill_folder(path):
    nested = os.path.join(path, "skill")
    return nested if os.path.isdir(nested) else path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="validate-portable-skill.py",
        description="Static checks for a promote-skill candidate. Never executes candidate content.")
    parser.add_argument("path", help="staging folder (manifest.json, REVIEW.md, skill/) or a skill folder")
    parser.add_argument("--deny-terms", metavar="FILE",
                        help="file of extra terms to flag, one per line; keep it outside the candidate")
    parser.add_argument("--digest", action="store_true", help="print the digest approval binds to and exit")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    tolerate_console_encoding()
    try:
        if not os.path.isdir(args.path):
            raise InputError("not a folder: %s" % args.path)
        if args.digest:
            folder = skill_folder(args.path)
            if os.path.islink(folder) or not os.path.isfile(os.path.join(folder, "SKILL.md")):
                raise InputError("no skill folder with SKILL.md under %s" % args.path)
            print(compute_digest(folder))
            return 0
        deny_terms = load_deny_terms(args.deny_terms) if args.deny_terms else []
        findings = validate_path(args.path, deny_terms)
    except (InputError, OSError) as exc:
        print("validate-portable-skill: error: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        folder = skill_folder(args.path)
        digest = None
        if not os.path.islink(folder) and os.path.isfile(os.path.join(folder, "SKILL.md")):
            digest = compute_digest(folder)
        print(json.dumps({
            "path": args.path,
            "kind": "staging" if os.path.isdir(os.path.join(args.path, "skill")) or
                    os.path.exists(os.path.join(args.path, "manifest.json")) else "skill",
            "digest": digest,
            "findings": [f.to_dict() for f in findings],
            "summary": {"errors": len(errors(findings)),
                        "warnings": sum(1 for f in findings if f.severity == "warning")},
        }, indent=2))
    else:
        print(format_text(args.path, findings))
    return 1 if errors(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
