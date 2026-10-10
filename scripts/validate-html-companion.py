#!/usr/bin/env python3
"""Structural validator for tobin-superpowers HTML companions.

Usage: python3 scripts/validate-html-companion.py COMPANION.html [--source SOURCE.md] [--json]

Checks the rules in skills/shared/html-companion-guide.md that can be checked
mechanically: the file is self-contained (no external assets), has the
required head, header band and footer source path, sits next to its source
Markdown with the same base name, and avoids known anti-patterns. It does not
judge layout quality or content accuracy, and never modifies any file.

Exit codes: 0 no errors (warnings allowed), 1 errors, 2 invalid invocation or
unreadable input.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Optional

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
DUMP_RATIO = 0.6
DUMP_MIN_CHARS = 300
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?['\"]?([^'\")\s;]+)", re.I)
RAW_MARKDOWN_RE = re.compile(r"^\s*(?:#{2,6}\s+\S|- \[[ xX]\]\s|\*\*[^*]+\*\*:)", re.M)
ABSOLUTE_PATH_RE = re.compile(r"^(?:/|~|[A-Za-z]:[\\/]|\\\\|file:)")

# Artifact type (from the containing directory) -> CSS classes its rendering
# priorities call for. Each inner tuple is "any of these classes".
TYPE_MARKERS = {
    "specs": ("design spec", (("toc",),)),
    "plans": ("implementation plan", (("checklist",),)),
    "reviews": ("code review report", (("toc",), ("pill",))),
    "run-summaries": ("run summary", (("pill",), ("checklist",))),
}

# Attributes that load a resource when the element is rendered.
ASSET_ATTRS = {
    "script": ("src",), "img": ("src", "srcset"), "source": ("src", "srcset"),
    "iframe": ("src",), "frame": ("src",), "embed": ("src",), "video": ("src", "poster"),
    "audio": ("src",), "track": ("src",), "object": ("data",), "input": ("src",),
    "image": ("href", "xlink:href"), "use": ("href", "xlink:href"),
    "feimage": ("href", "xlink:href"), "base": ("href",),
}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    line: Optional[int]
    message: str
    suggestion: str

    def to_dict(self):
        return asdict(self)


class CompanionReadError(ValueError):
    """The companion or its source could not be read."""


def is_external(url):
    """True if loading url would reach outside the file (data: and #frag are inline)."""
    url = url.strip()
    return bool(url) and not url.startswith("#") and not url.lower().startswith("data:")


def srcset_urls(value):
    return [part.strip().split()[0] for part in value.split(",") if part.strip()]


class CompanionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.doctype = False
        self.charset = False
        self.viewport = False
        self.title = ""
        self.inline_scripts = []  # line numbers
        self.external = []  # (line, url, what)
        self.classes = set()
        self.stack = []  # open element names
        self.header_depth = None
        self.header_has_h1 = False
        self.header_text = []
        self.footer_depth = None
        self.footer_text = []
        self.footer_line = None
        self.pre_texts = []
        self.text_total = 0
        self.prose_text = []  # (line, text) outside pre/code/script/style
        self._in_title = False

    # --- helpers
    def inside(self, *names):
        return any(name in self.stack for name in names)

    def check_css(self, css, line, where):
        for match in CSS_IMPORT_RE.finditer(css):
            self.external.append((line, match.group(1), "@import in %s" % where))
        for match in CSS_URL_RE.finditer(css):
            if is_external(match.group(2)) and not re.search(r"@import\s+url\(\s*['\"]?" + re.escape(match.group(2)), css):
                self.external.append((line, match.group(2), "url() in %s" % where))
        if "@font-face" in css.lower():
            self.external.append((line, "@font-face", "web font in %s" % where))

    # --- parser callbacks
    def handle_decl(self, decl):
        if decl.lower().strip() == "doctype html":
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        a = {k.lower(): (v or "") for k, v in attrs}
        self.classes.update(a.get("class", "").split())
        if tag == "meta":
            if "charset" in a or "charset=" in a.get("content", "").lower():
                self.charset = True
            if a.get("name", "").lower() == "viewport":
                self.viewport = True
        elif tag == "link" and a.get("href") and is_external(a["href"]):
            self.external.append((line, a["href"], "<link rel=%s>" % (a.get("rel") or "?")))
        for attr in ASSET_ATTRS.get(tag, ()):
            value = a.get(attr)
            if not value:
                continue
            urls = srcset_urls(value) if attr == "srcset" else [value]
            for url in urls:
                if tag == "use" and url.startswith("#"):
                    continue
                if is_external(url) or tag == "base":
                    self.external.append((line, url, "<%s %s>" % (tag, attr)))
        if a.get("style"):
            self.check_css(a["style"], line, "style attribute")
        if tag == "script" and "src" not in a:
            self.inline_scripts.append(line)
        if tag == "title":
            self._in_title = True
        if tag == "header" and self.header_depth is None:
            self.header_depth = len(self.stack)
        if tag == "h1" and self.header_depth is not None:
            self.header_has_h1 = True
        if tag == "footer" and self.footer_depth is None:
            self.footer_depth = len(self.stack)
            self.footer_line = line
        if tag == "pre":
            self.pre_texts.append("")
        if tag not in ("br", "img", "meta", "link", "hr", "input", "source", "track", "base", "col", "wbr", "area", "embed", "param"):
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.stack:
            while self.stack:
                closed = self.stack.pop()
                if closed == tag:
                    break
        if self.header_depth is not None and tag == "header" and len(self.stack) <= self.header_depth:
            self.header_depth = -1  # closed; keep collected text
        if self.footer_depth is not None and tag == "footer" and len(self.stack) <= self.footer_depth:
            self.footer_depth = -1

    def handle_data(self, data):
        line = self.getpos()[0]
        if self._in_title:
            self.title += data
        if self.stack and self.stack[-1] == "style":
            self.check_css(data, line, "<style>")
            return
        if self.inside("script", "style", "head") and not self._in_title:
            return
        self.text_total += len(data.strip())
        if self.header_depth is not None and self.header_depth >= 0:
            self.header_text.append(data)
        if self.footer_depth is not None and self.footer_depth >= 0:
            self.footer_text.append(data)
        if "pre" in self.stack and self.pre_texts:
            self.pre_texts[-1] += data
        elif not self.inside("code"):
            self.prose_text.append((line, data))


def artifact_type(*paths):
    for path in paths:
        if path:
            parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
            for part in reversed(parts[:-1]):
                if part in TYPE_MARKERS:
                    return part
    return None


def footer_source(parser):
    text = " ".join(" ".join(parser.footer_text).split())
    match = re.search(r"Source:\s*(\S+\.md)\b", text)
    return match.group(1) if match else None


def path_suffix_matches(source_path, footer_path):
    source_parts = os.path.normpath(os.path.abspath(source_path)).split(os.sep)
    footer_parts = [p for p in footer_path.replace("\\", "/").split("/") if p not in ("", ".")]
    return bool(footer_parts) and source_parts[-len(footer_parts):] == footer_parts


def validate_text(text, html_path=None, source_path=None):
    """Validate companion HTML text. Paths are only used for name/location checks."""
    parser = CompanionParser()
    parser.feed(text)
    parser.close()
    findings = []

    def add(rule, severity, line, message, suggestion):
        findings.append(Finding(rule, severity, line, message, suggestion))

    for line, url, what in parser.external:
        add("external-resource", "error", line,
            "External resource %s: %s" % (what, url),
            "Inline it (CSS in <style>, images as data: URIs) or remove it; use system fonts. "
            "The companion must open offline by double-click.")
    if not parser.doctype:
        add("doctype", "error", 1, "Missing <!DOCTYPE html>.", "Start the file with <!DOCTYPE html>.")
    if not parser.charset:
        add("charset", "error", None, "Missing <meta charset>.", 'Add <meta charset="utf-8"> in <head>.')
    if not parser.title.strip():
        add("title", "error", None, "Missing or empty <title>.", "Use the document title from the markdown H1.")
    if not parser.viewport:
        add("viewport", "warning", None, "Missing viewport meta tag.",
            'Add <meta name="viewport" content="width=device-width, initial-scale=1">.')

    header = " ".join(" ".join(parser.header_text).split())
    if parser.header_depth is None or not parser.header_has_h1:
        add("header", "error", None, "Missing header band with an <h1> title.",
            'Add <header class="companion-header"><h1>Title</h1><div class="meta">Companion to the … · YYYY-MM-DD</div></header>.')
    else:
        if "companion to" not in header.lower():
            add("header", "error", None, "Header does not label the page as a companion.",
                "Add 'Companion to the <artifact> — open the .md for the agent-facing source'.")
        if not DATE_RE.search(header):
            add("header", "error", None, "Header has no ISO generation date.",
                "Add the date the companion was generated, e.g. 2026-05-11.")

    source_ref = footer_source(parser)
    if parser.footer_depth is None or source_ref is None:
        add("footer-source", "error", parser.footer_line,
            "Missing footer with 'Source: <relative path>.md'.",
            "Add <footer class=\"companion-footer\">Source: <code>docs/…/file.md</code></footer>.")
    elif ABSOLUTE_PATH_RE.search(source_ref) or ".." in source_ref.replace("\\", "/").split("/"):
        add("footer-source", "error", parser.footer_line,
            "Footer source path is not a relative project path: %s" % source_ref,
            "Use the repository-relative path, e.g. docs/superpowers/specs/x.md.")
    else:
        expected_name = (os.path.splitext(os.path.basename(html_path))[0] + ".md") if html_path else None
        if expected_name and os.path.basename(source_ref) != expected_name:
            add("footer-source", "error", parser.footer_line,
                "Footer source %s does not match the companion name (expected …/%s)." % (source_ref, expected_name),
                "Point the footer at the markdown this companion was generated from.")
        elif source_path and not path_suffix_matches(source_path, source_ref):
            add("footer-source", "error", parser.footer_line,
                "Footer source %s is not the given source %s." % (source_ref, source_path),
                "Use the source markdown's path relative to the project root.")

    if html_path:
        html_dir, html_stem = os.path.split(os.path.abspath(html_path))
        html_stem = os.path.splitext(html_stem)[0]
        if source_path:
            src_dir, src_stem = os.path.split(os.path.abspath(source_path))
            if (src_dir, os.path.splitext(src_stem)[0]) != (html_dir, html_stem):
                add("filename", "error", None,
                    "Companion %s is not next to its source with the same base name." % os.path.basename(html_path),
                    "Save it as %s.html beside the markdown." % os.path.splitext(src_stem)[0])
        elif not os.path.isfile(os.path.join(html_dir, html_stem + ".md")):
            add("filename", "warning", None,
                "No sibling %s.md found next to the companion." % html_stem,
                "Companions sit next to their source markdown with the same base name.")

    for line in parser.inline_scripts:
        add("script", "warning", line, "Inline <script> present.",
            "Plain HTML and CSS should cover companions; remove JavaScript unless essential.")

    largest_pre = max((len(t.strip()) for t in parser.pre_texts), default=0)
    if parser.text_total >= DUMP_MIN_CHARS and largest_pre / parser.text_total > DUMP_RATIO:
        add("markdown-dump", "warning", None,
            "One <pre> block holds %d%% of the page text." % round(100 * largest_pre / parser.text_total),
            "Re-lay the content for human reading (summary, sections, callouts) instead of dumping markdown.")
    else:
        raw = next(((line, t) for line, t in parser.prose_text if RAW_MARKDOWN_RE.search(t)), None)
        if raw:
            add("markdown-dump", "warning", raw[0],
                "Raw markdown syntax in page text: %r" % raw[1].strip()[:40],
                "Convert markdown headings, checkboxes, and bold labels to HTML.")

    kind = artifact_type(source_path, html_path)
    if kind:
        label, required = TYPE_MARKERS[kind]
        for options in required:
            if not parser.classes.intersection(options):
                add("type-structure", "warning", None,
                    "%s %s companion usually has a .%s element (per its rendering priorities)."
                    % ("An" if label[0] in "aeiou" else "A", label, options[0]),
                    "Follow the 'Companion: %s' section of the html-companion skill." % label.title())

    return sorted(findings, key=lambda f: (f.line or 0, SEVERITY_ORDER[f.severity], f.rule))


def read_text(path, what):
    if not os.path.isfile(path):
        raise CompanionReadError("%s is not a readable file: %s" % (what, path))
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise CompanionReadError("%s is not valid UTF-8: %s" % (what, path))
    except OSError as exc:
        raise CompanionReadError("cannot read %s: %s" % (path, exc.strerror or exc))
    if "\x00" in text:
        raise CompanionReadError("%s contains NUL bytes: %s" % (what, path))
    return text


def validate_file(path, source=None):
    """Validate a companion file without modifying anything. Raises CompanionReadError."""
    text = read_text(path, "companion")
    if source is not None:
        read_text(source, "source")
    return validate_text(text, html_path=path, source_path=source)


def errors(findings):
    return [f for f in findings if f.severity == "error"]


def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def format_text(display_path, findings):
    lines = []
    for f in findings:
        where = "%s:%d" % (display_path, f.line) if f.line else display_path
        lines.append("%s: %s [%s] %s\n    fix: %s" % (where, f.severity, f.rule, f.message, f.suggestion))
    counts = [sum(1 for f in findings if f.severity == s) for s in ("error", "warning")]
    lines.append("Summary: %s, %s — %s" % (plural(counts[0], "error"), plural(counts[1], "warning"), display_path))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="validate-html-companion.py",
        description="Structural check of a tobin-superpowers HTML companion.")
    parser.add_argument("path", help="companion .html file")
    parser.add_argument("--source", help="source markdown the companion was generated from")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        findings = validate_file(args.path, args.source)
    except CompanionReadError as exc:
        print("validate-html-companion: error: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({
            "file": args.path,
            "findings": [f.to_dict() for f in findings],
            "summary": {"errors": len(errors(findings)),
                        "warnings": sum(1 for f in findings if f.severity == "warning")},
        }, indent=2))
    else:
        print(format_text(args.path, findings))
    return 1 if errors(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
