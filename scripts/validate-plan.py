#!/usr/bin/env python3
"""Advisory structural validator for superpowers implementation plans.

Usage: python3 scripts/validate-plan.py PLAN.md [--json]

Checks each "Task N" section for the information a skilled developer needs
to execute it without AI assistance: file paths, interfaces, ordered steps,
concrete test cases, verification commands, and pattern references. It also
flags placeholders. It checks structure only, never semantic correctness,
and never modifies the plan.

Exit codes: 0 no errors (warnings allowed), 1 errors, 2 invalid invocation
or unreadable/malformed input.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import List, Optional

PLAN_DIR_PARTS = ("docs", "superpowers", "plans")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
LONG_CODE_LINES = 40


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    line: Optional[int]
    task: Optional[int]
    message: str
    suggestion: str

    def to_dict(self):
        return asdict(self)


class PlanReadError(ValueError):
    """The plan file could not be read as UTF-8 Markdown."""


# --- Markdown structure -----------------------------------------------------

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TASK_TITLE_RE = re.compile(r"^(?:\*\*)?Task\s+(\d+)\b\s*(?:[:.\-–—]|\*\*|$)", re.I)
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")
BACKTICK_RE = re.compile(r"`([^`]+)`")
SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh", "powershell", "ps1", "pwsh", "cmd", "bat"}


@dataclass
class Line:
    number: int  # 1-based
    text: str
    in_code: bool
    code_lang: str = ""


@dataclass
class CodeBlock:
    start: int  # line number of the opening fence
    length: int


@dataclass
class Task:
    number: int
    line: int
    lines: List[Line]


def scan(text):
    """Return (lines, code_blocks) with fenced-code membership resolved.

    Plans often nest fences without lengthening the outer one, e.g. a ```bash
    block inside a ```markdown block. A fence with an info string inside an
    open block is treated as a nested opening; a bare fence closes the
    innermost block. Only outermost blocks are reported in code_blocks.
    """
    lines, blocks = [], []
    stack = []  # [(char, length, lang, start)]
    count = 0
    for i, raw in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(raw)
        if stack:
            char, length, lang, start = stack[-1]
            stripped = raw.strip()
            if stripped and set(stripped) == {char} and len(stripped) >= length:
                stack.pop()
                if not stack:
                    blocks.append(CodeBlock(start, count))
            elif match and match.group(2) and match.group(1)[0] == char:
                stack.append((char, len(match.group(1)), match.group(2).lower(), i))
                count += 1
            else:
                count += 1
            lines.append(Line(i, raw, True, (stack[-1] if stack else (char, length, lang))[2]))
            continue
        if match:
            marker = match.group(1)
            stack.append((marker[0], len(marker), match.group(2).lower(), i))
            count = 0
            lines.append(Line(i, raw, True, stack[-1][2]))
            continue
        lines.append(Line(i, raw, False))
    if stack:
        blocks.append(CodeBlock(stack[0][3], count))
    return lines, blocks


def split_tasks(lines):
    tasks, current, level = [], None, 0
    for line in lines:
        heading = None if line.in_code else HEADING_RE.match(line.text)
        if heading:
            depth = len(heading.group(1))
            title = TASK_TITLE_RE.match(heading.group(2))
            if title and 2 <= depth <= 4:
                current = Task(int(title.group(1)), line.number, [])
                level = depth
                tasks.append(current)
                continue
            if current is not None and depth <= level:
                current = None
        if current is not None:
            current.lines.append(line)
    return tasks


def prose(line):
    """Line text with inline code removed; empty for code-fence lines."""
    return "" if line.in_code else INLINE_CODE_RE.sub(" ", line.text)


# --- Per-task checks ---------------------------------------------------------

FILE_LABEL_RE = re.compile(r"^\W*(create|modify|test|tests|files?|delete|rename)\b", re.I)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
NO_FILES_RE = re.compile(
    r"^\W*files?\W*:?\W*(?:none|n/a)\b|\bno\s+(?:repo(?:sitory)?|file|code)\s+changes\b", re.I)
DOC_PATH_RE = re.compile(r"(?:^|/)docs?/|\.(?:md|mdx|markdown|rst|txt|adoc)$", re.I)
INEXACT_RE = re.compile(r"\*|<[^>]*>|\.\.\.|…|\betc\b|path/to/", re.I)

INTERFACE_LABEL_RE = re.compile(
    r"\b(interfaces?|signatures?|produces|consumes|public api|api)\b\**\s*:", re.I)
NO_INTERFACE_RE = re.compile(
    r"\bno\s+(?:new\s+|public\s+|changed\s+)?(interfaces?|signatures?|apis?)\b", re.I)

STEP_RE = re.compile(r"^\s*(?:[-*+]\s+\[[ xX]\]\s+|\d+[.)]\s+|\W*step\s+\d+\b)", re.I)

TEST_CASE_RES = (
    re.compile(r"\bassert\w*\s*[(\w`]"),
    re.compile(r"\bexpect\s*\("),
    re.compile(r"==|!=|\bto(?:Be|Equal|Throw)\w*\("),
    re.compile(r"\b(?:raises?|throws?)\s+`?[\w.]*(?:Error|Exception|Exit)\w*", re.I),
    re.compile(r"\b(?:returns?|yields?)\s+`[^`]+`", re.I),
    re.compile(r"\bis\s+(?:not\s+)?(?:None|True|False|null|undefined|nil)\b"),
)
ARROW_CASE_RE = re.compile(r"\S\s*(?:→|=>)\s*\S")
EXPECTED_WORD_RE = re.compile(r"\bexpected\b", re.I)
NO_TESTS_RE = re.compile(
    r"\bno\s+(?:new\s+|automated\s+|unit\s+)?tests?\b\s*(?:[:(—–-]|needed|required|because)",
    re.I)

COMMAND_NAMES = (
    r"python3?|py|pytest|tox|nox|uv|poetry|pipenv|pip|npm|npx|pnpm|yarn|bun|node|deno|"
    r"jest|vitest|mocha|go|cargo|make|mvn|gradle|gradlew|dotnet|bundle|rake|rspec|ruby|"
    r"php|phpunit|composer|mix|swift|xcodebuild|ctest|cmake|bazel|bash|sh|zsh|pwsh|"
    r"curl|grep|diff|jq|docker|claude"
)
COMMAND_RE = re.compile(
    r"^(?:\$\s*)?(?:[A-Z_]+=\S+\s+)*(?:(?:" + COMMAND_NAMES + r")(?=\s+[^\s=:(]|$)|\.{1,2}/\S+|\S+\.(?:sh|ps1|bat|cmd)\b)"
)
EXPECTED_RES = (
    re.compile(r"\bexpect(?:ed|s)?\b|\bshould\s+(?:pass|fail|print|output|show|return)", re.I),
    re.compile(r"→|=>"),
    re.compile(r"\b\d+\s+(?:passed|tests? pass(?:es|ed)?|ok)\b|\ball\s+(?:tests\s+)?pass", re.I),
    re.compile(r"\b(?:PASS|PASSED|FAIL|FAILED|OK)\b"),
    re.compile(r"\bexit(?:s|\s+code)?\s*(?:status\s*)?[=:]?\s*\d\b|\bsucceeds?\b", re.I),
    re.compile(r"\b(?:prints?|outputs?|shows?|returns?)\b", re.I),
)

PATTERN_RE = re.compile(
    r"\bpatterns?\b|\bfollows?\b|\bmirrors?\b|\bmirroring\b|\bmodell?ed\s+(?:on|after)\b|"
    r"\bsame\s+(?:approach|structure|style|shape)\s+as\b|\bbased\s+on\b|\bconventions?\b",
    re.I)


def is_path_like(token):
    token = token.strip().split()[0] if token.strip() else ""
    token = re.sub(r":\d+(?:-\d+)?$", "", token)
    if not token or any(c in token for c in "()=,;\"'"):
        return False
    return "/" in token or "\\" in token or re.search(r"\.[A-Za-z0-9]{1,10}$", token) is not None


def task_paths(task):
    """Backticked path-like tokens on file-label lines of a task."""
    paths = []
    for line in task.lines:
        if not line.in_code and FILE_LABEL_RE.match(line.text):
            paths.extend(t for t in BACKTICK_RE.findall(line.text) if is_path_like(t))
    return paths


def is_docs_only(task):
    paths = [re.sub(r":\d+(?:-\d+)?$", "", p.split()[0]) for p in task_paths(task)]
    return bool(paths) and all(DOC_PATH_RE.search(p) for p in paths)


def check_files(task):
    # A path counts when its line starts with a file label (Create/Modify/Test/
    # Files...) or is a list item directly under a bare "Files:" label.
    findings, found, in_files_list = [], False, False
    for line in task.lines:
        text = line.text
        if line.in_code or not text.strip():
            continue
        labelled = FILE_LABEL_RE.match(text) is not None
        if not labelled and not (in_files_list and LIST_ITEM_RE.match(text)):
            in_files_list = False
            continue
        paths = [t for t in BACKTICK_RE.findall(text) if is_path_like(t)]
        if NO_FILES_RE.search(text):
            found = True
            continue
        if labelled and not paths and re.match(r"^\W*files?\b", text, re.I):
            in_files_list = True
            continue
        for path in paths:
            found = True
            if INEXACT_RE.search(path):
                findings.append(Finding(
                    "inexact-path", "warning", line.number, task.number,
                    "Path `%s` is not exact (wildcard or placeholder)." % path,
                    "Name the exact file, e.g. `src/module/file.py` or `src/file.py:10-20`."))
    if not found:
        findings.append(Finding(
            "files", "error", task.line, task.number,
            "No Create/Modify/Test file paths found.",
            "Add a **Files:** list with backticked paths, e.g. "
            "`- Modify: `src/app.py:10-20`` and `- Test: `tests/test_app.py``."))
    return findings


def check_interfaces(task):
    for line in task.lines:
        text = line.text if not line.in_code else ""
        if INTERFACE_LABEL_RE.search(text) or NO_INTERFACE_RE.search(text):
            return []
    return [Finding(
        "interfaces", "error", task.line, task.number,
        "No interfaces listed and no statement that none are introduced.",
        "Add **Interfaces:** with exact signatures (name, parameters, return type), "
        "or write 'Interfaces: none (no new interfaces)'.")]


def check_steps(task):
    steps = sum(1 for line in task.lines if not line.in_code and STEP_RE.match(line.text))
    if steps >= 2:
        return []
    return [Finding(
        "steps", "error", task.line, task.number,
        "Fewer than two ordered steps found.",
        "Break the task into ordered steps (`- [ ] **Step 1: ...**` or a numbered list), "
        "one action each.")]


def has_test_case(line):
    text = line.text
    if any(r.search(text) for r in TEST_CASE_RES):
        return True
    return ARROW_CASE_RE.search(text) is not None and not EXPECTED_WORD_RE.search(text)


def check_tests(task):
    for line in task.lines:
        if has_test_case(line) or (not line.in_code and NO_TESTS_RE.search(line.text)):
            return []
    docs_only = is_docs_only(task)
    return [Finding(
        "tests", "warning" if docs_only else "error", task.line, task.number,
        "No concrete test assertions or test cases found%s."
        % (" (documentation-only task)" if docs_only else ""),
        "State each test's inputs and expected result, e.g. "
        "`parse(\"1,2\") == [1, 2]` or `load(\"x\")` raises `FileNotFoundError`; "
        "or write 'No tests: <reason>'.")]


def is_command(text):
    return COMMAND_RE.match(text.strip()) is not None


def check_verification(task):
    has_command = False
    for line in task.lines:
        if line.in_code:
            if line.code_lang in SHELL_LANGS and not FENCE_RE.match(line.text) and is_command(line.text):
                has_command = True
        elif any(is_command(snippet) for snippet in BACKTICK_RE.findall(line.text)):
            has_command = True
    if not has_command:
        return [Finding(
            "verification", "error", task.line, task.number,
            "No verification command found.",
            "Add a step with the exact command and expected result, e.g. "
            "'Run `python3 -m unittest tests.test_app -v` → Expected: 3 passed'.")]
    text = "\n".join(line.text for line in task.lines if not line.in_code)
    text = re.sub(r"\bexpected\s*:\s*$", "", text, flags=re.I | re.M)
    if any(r.search(text) for r in EXPECTED_RES):
        return []
    return [Finding(
        "expected-result", "warning", task.line, task.number,
        "Verification command has no stated expected result.",
        "State what success looks like, e.g. 'Expected: PASS', '3 passed', or the exact output.")]


def check_pattern(task):
    for line in task.lines:
        if not line.in_code and PATTERN_RE.search(line.text):
            return []
    return [Finding(
        "pattern", "warning", task.line, task.number,
        "No existing codebase pattern referenced.",
        "Add '**Pattern to follow:** `path/file.py:LINE`' naming similar existing code, "
        "or 'Pattern to follow: none (new pattern)'.")]


TASK_CHECKS = (check_files, check_interfaces, check_steps, check_tests,
               check_verification, check_pattern)


# --- Document-wide checks ----------------------------------------------------

PLACEHOLDER_RES = (
    # Bare markers, but not quoted mentions ("TBD") or talk about them ("TODO markers").
    re.compile(r"(?<![\"'\u201c\u2018])\b(?:TBD|TODO|FIXME|XXX)\b(?![\"'\u201d\u2019])"
               r"(?!\s+(?:markers?|comments?|items?|placeholders?|tags?)\b)"),
    re.compile(r"\bimplement(?:ed)?\s+later\b|\bfill\s+in\s+(?:the\s+)?details\b|"
               r"\bwrite\s+tests\s+for\s+the\s+above\b|\bto\s+be\s+determined\b", re.I),
)
VAGUE_RES = (
    re.compile(r"\badd\s+(?:appropriate\s+|proper\s+|necessary\s+)?(?:error\s+handling|validation)\b"
               r"|\bhandle\s+(?:all\s+|any\s+|the\s+)?edge\s+cases\b|\bsimilar\s+to\s+task\s+\d+\b",
               re.I),
)


def task_for_line(tasks, number):
    for task in tasks:
        if task.lines and task.line <= number <= task.lines[-1].number:
            return task.number
        if not task.lines and number == task.line:
            return task.number
    return None


def check_phrases(lines, tasks):
    findings = []
    for line in lines:
        text = prose(line)
        if not text.strip():
            continue
        placeholder = next((m for r in PLACEHOLDER_RES for m in [r.search(text)] if m), None)
        if placeholder:
            findings.append(Finding(
                "placeholder", "error", line.number, task_for_line(tasks, line.number),
                "Placeholder '%s' left in the plan." % placeholder.group(0),
                "Replace it with the concrete decision, value, or test the implementer needs."))
            continue
        vague = next((m for r in VAGUE_RES for m in [r.search(text)] if m), None)
        if vague:
            findings.append(Finding(
                "vague-instruction", "warning", line.number, task_for_line(tasks, line.number),
                "Vague instruction '%s'." % vague.group(0),
                "Name the specific cases, errors, or rules and the test that covers each; "
                "restate what a task needs instead of 'similar to Task N'."))
    return findings


def check_long_code(blocks, tasks):
    return [Finding(
        "long-code", "info", block.start, task_for_line(tasks, block.start),
        "Code block is %d lines long." % block.length,
        "For routine changes, prefer signatures, test assertions, and pseudocode "
        "over full listings.")
        for block in blocks if block.length > LONG_CODE_LINES]


# --- Public API --------------------------------------------------------------

def sort_findings(findings):
    return sorted(findings, key=lambda f: (f.line or 0, SEVERITY_ORDER[f.severity], f.rule))


def validate_text(text):
    """Validate plan Markdown text. Returns a sorted list of Finding."""
    lines, blocks = scan(text)
    tasks = split_tasks(lines)
    if not tasks:
        return [Finding(
            "no-tasks", "error", None, None,
            "No implementation tasks found.",
            "Add task sections headed '### Task 1: <name>', one per independently "
            "testable deliverable.")]
    findings = []
    for task in tasks:
        for check in TASK_CHECKS:
            findings.extend(check(task))
    findings.extend(check_phrases(lines, tasks))
    findings.extend(check_long_code(blocks, tasks))
    return sort_findings(findings)


def in_plan_dir(path):
    parts = [p.lower() for p in os.path.normpath(os.path.abspath(path)).split(os.sep)]
    n = len(PLAN_DIR_PARTS)
    return any(tuple(parts[i:i + n]) == PLAN_DIR_PARTS for i in range(len(parts) - n))


def read_plan(path):
    if not os.path.isfile(path):
        raise PlanReadError("not a readable file: %s" % path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise PlanReadError("not valid UTF-8 text: %s" % path)
    except OSError as exc:
        raise PlanReadError("cannot read %s: %s" % (path, exc.strerror or exc))
    if "\x00" in text:
        raise PlanReadError("contains NUL bytes, not Markdown: %s" % path)
    return text


def validate_file(path):
    """Validate a plan file without modifying it. Raises PlanReadError."""
    findings = validate_text(read_plan(path))
    if not in_plan_dir(path):
        findings.insert(0, Finding(
            "location", "info", None, None,
            "File is not under docs/superpowers/plans/; validated anyway.",
            "Save plans under docs/superpowers/plans/ so the hook validates them automatically."))
    return findings


def errors(findings):
    return [f for f in findings if f.severity == "error"]


def summarize(findings):
    return {s + ("s" if s != "info" else ""): sum(1 for f in findings if f.severity == s)
            for s in ("error", "warning", "info")}


def format_finding(display_path, f):
    where = "%s:%d" % (display_path, f.line) if f.line else display_path
    task = " Task %d:" % f.task if f.task is not None else ""
    return "%s: %s [%s]%s %s\n    fix: %s" % (where, f.severity, f.rule, task, f.message, f.suggestion)


def format_summary(findings):
    counts = summarize(findings)
    return "%d errors, %d warnings, %d info" % (counts["errors"], counts["warnings"], counts["info"])


def format_text(display_path, findings):
    body = [format_finding(display_path, f) for f in findings]
    body.append("Summary: %s — %s" % (format_summary(findings), display_path))
    return "\n".join(body)


def format_json(display_path, findings):
    return json.dumps({
        "file": display_path,
        "findings": [f.to_dict() for f in findings],
        "summary": summarize(findings),
    }, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="validate-plan.py",
        description="Advisory structural check of a superpowers implementation plan.")
    parser.add_argument("path", help="Markdown plan, e.g. docs/superpowers/plans/x.md")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        findings = validate_file(args.path)
    except PlanReadError as exc:
        print("validate-plan: error: %s" % exc, file=sys.stderr)
        return 2
    print(format_json(args.path, findings) if args.json else format_text(args.path, findings))
    return 1 if errors(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
