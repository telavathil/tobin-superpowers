#!/usr/bin/env python3
"""Guided, local import of an approved promote-skill candidate.

Usage: python3 scripts/import-portable-skill.py STAGING --dest CHECKOUT
           [--apply] [--allow-overwrite] [--worktree PATH] [--branch NAME]
           [--skip-plugin-validate] [--json]

Without --apply it only prints the plan. With --apply it creates a feature
branch (in CHECKOUT, or in a new git worktree at PATH), copies exactly the
manifest's files from STAGING/skill/ into skills/<name>/, and runs the
candidate validator, the repository's test suite and, when the claude CLI is
on PATH, plugin validation. It never runs the candidate's own scripts or
validation commands, and never commits, pushes, tags or opens a pull request.

Refuses unless the candidate validates, its status is approved by the user,
the approved digest still matches, and transfer is authorized. Also refuses a
destination that is not the root of a tobin-superpowers checkout, has
uncommitted changes (use --worktree), already has the branch, or already has
skills/<name>/ (use --allow-overwrite only after the user approves replacing
it). Built-in and official superpowers skill names are never replaced.

Exit codes: 0 plan ready or import applied with checks passing, 1 refused or
a check failed, 2 invalid invocation or destination unavailable.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import List, Optional

sys.dont_write_bytecode = True
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
NESTED_ENV = "PROMOTE_SKILL_NESTED_CHECK"
PLUGIN_NAME = "tobin-superpowers"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_portable_skill", os.path.join(SCRIPTS_DIR, "validate-portable-skill.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VP = load_validator()


class DestinationUnavailable(ValueError):
    """The destination checkout does not exist or is not a folder."""


@dataclass
class Plan:
    staging: str
    dest: str
    name: Optional[str] = None
    target: Optional[str] = None
    branch: Optional[str] = None
    worktree: Optional[str] = None
    workdir: Optional[str] = None
    files: List[str] = field(default_factory=list)
    digest: Optional[str] = None
    allow_overwrite: bool = False
    overwrite: bool = False
    current_branch: Optional[str] = None
    dirty_paths: int = 0
    publication_authorized: bool = False
    refusals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.refusals


@dataclass
class Result:
    plan: Plan
    applied: bool = False
    copied: List[str] = field(default_factory=list)
    checks: List[dict] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self):
        return self.applied and not self.problems and all(c["status"] != "failed" for c in self.checks)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def inside(path, root):
    path, root = (os.path.normcase(os.path.realpath(p)) for p in (path, root))
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def load_manifest(staging):
    try:
        with open(os.path.join(staging, "manifest.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def check_candidate(plan):
    findings = VP.validate_path(plan.staging)
    failing = VP.errors(findings)
    if failing:
        rules = sorted({f.rule for f in failing})
        plan.refusals.append("candidate validation has %d error(s): %s; fix them and re-review"
                             % (len(failing), ", ".join(rules)))
    manifest = load_manifest(plan.staging)
    if manifest is None:
        plan.refusals.append("manifest.json is missing or invalid")
        return None
    status = manifest.get("status")
    approval = manifest.get("approval") if isinstance(manifest.get("approval"), dict) else {}
    if status == "blocked":
        plan.refusals.append("candidate is blocked; it cannot be imported")
    elif status != "approved":
        plan.refusals.append("candidate is not approved (status %s); only the user's explicit approval "
                             "after review allows import" % status)
    if approval.get("approved_by_user") is not True:
        plan.refusals.append("approval.approved_by_user is not true")
    if approval.get("transfer_authorized") is not True:
        plan.refusals.append("transfer to the personal repository is not authorized; ask the user "
                             "separately from approval")
    plan.publication_authorized = approval.get("publication_authorized") is True
    plan.digest = approval.get("digest")
    if VP.valid_name(manifest.get("name")):
        plan.name = manifest["name"]
    files = manifest.get("files")
    if isinstance(files, list) and all(isinstance(f, str) and not VP.unsafe_relpath(f) for f in files):
        plan.files = list(files)
    elif not any("path-escape" in r for r in plan.refusals):
        plan.refusals.append("manifest files are invalid (path-escape)")
    return manifest


def check_destination(plan):
    dest = plan.dest
    top = git(dest, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        plan.refusals.append("destination is not a git checkout")
        return
    same = lambda a, b: os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))  # noqa: E731
    if not same(top.stdout.strip(), dest):
        plan.refusals.append("destination must be the root of the checkout, not a subfolder")
        return
    try:
        with open(os.path.join(dest, ".claude-plugin", "plugin.json"), encoding="utf-8") as handle:
            plugin_name = json.load(handle).get("name")
    except (OSError, ValueError, AttributeError):
        plugin_name = None
    if plugin_name != PLUGIN_NAME:
        plan.refusals.append("destination is not a %s checkout (.claude-plugin/plugin.json)" % PLUGIN_NAME)
        return
    plan.current_branch = git(dest, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    status = git(dest, "status", "--porcelain", "--untracked-files=all")
    plan.dirty_paths = len(status.stdout.splitlines())
    if plan.dirty_paths and not plan.worktree:
        plan.refusals.append("destination has %d uncommitted change(s); commit or stash them yourself, "
                             "or pass --worktree PATH to work in a separate worktree" % plan.dirty_paths)
    if plan.branch and git(dest, "rev-parse", "--verify", "--quiet", "refs/heads/" + plan.branch).returncode == 0:
        plan.refusals.append("branch %s already exists; choose another with --branch" % plan.branch)
    if plan.worktree and os.path.lexists(plan.worktree):
        plan.refusals.append("worktree path already exists: %s" % plan.worktree)

    skills = os.path.join(dest, "skills")
    if os.path.islink(skills) or not os.path.isdir(skills):
        plan.refusals.append("skills/ is missing or is a symbolic link")
        return
    if not plan.name:
        return
    if plan.name in VP.RESERVED_NAMES:
        plan.refusals.append("skills/%s is a built-in or official superpowers skill and is never replaced" % plan.name)
        return
    target = os.path.join(dest, "skills", plan.name)
    if os.path.islink(target):
        plan.refusals.append("skills/%s is a symbolic link; it is never followed or replaced" % plan.name)
    elif os.path.lexists(target):
        if plan.allow_overwrite and os.path.isdir(target):
            plan.overwrite = True
            plan.notes.append("skills/%s already exists and will be replaced (overwrite approved)" % plan.name)
        else:
            plan.refusals.append("skills/%s already exists; pass --allow-overwrite only after the user "
                                 "approves replacing it" % plan.name)


def plan_import(staging, dest, allow_overwrite=False, worktree=None, branch=None):
    """Decide whether and how to import; changes nothing."""
    if not os.path.isdir(staging):
        raise FileNotFoundError("staging folder not found: %s" % staging)
    if not os.path.isdir(dest):
        raise DestinationUnavailable(dest)
    plan = Plan(staging=os.path.abspath(staging), dest=os.path.abspath(dest),
                allow_overwrite=allow_overwrite,
                worktree=os.path.abspath(worktree) if worktree else None)
    check_candidate(plan)
    if plan.name:
        plan.branch = branch or "promote-skill/" + plan.name
    check_destination(plan)
    if plan.name:
        plan.workdir = plan.worktree or plan.dest
        plan.target = os.path.join(plan.workdir, "skills", plan.name)
    if not plan.publication_authorized:
        plan.notes.append("Publication is not authorized: do not push or open a pull request")
    return plan


def copy_files(plan, result):
    source_root = os.path.realpath(os.path.join(plan.staging, "skill"))
    if plan.overwrite and os.path.isdir(plan.target) and not os.path.islink(plan.target):
        shutil.rmtree(plan.target)
    os.makedirs(plan.target)
    target_root = os.path.realpath(plan.target)
    for rel in plan.files:
        src = os.path.join(source_root, *rel.split("/"))
        dst = os.path.join(target_root, *rel.split("/"))
        if os.path.islink(src) or not os.path.isfile(src) or not inside(src, source_root):
            raise ValueError("refusing to copy %s: not a regular file inside the candidate" % rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not inside(os.path.dirname(dst), target_root) or os.path.lexists(dst):
            raise ValueError("refusing to write %s outside or over the target" % rel)
        shutil.copyfile(src, dst)
        shutil.copymode(src, dst)
        result.copied.append(rel)


def tail(text, lines=25):
    return "\n".join(text.strip().splitlines()[-lines:])


def run_post_import_checks(plan, result, plugin_validate=True):
    findings = VP.validate_path(plan.target)
    failing = VP.errors(findings)
    result.checks.append({
        "name": "candidate validation",
        "status": "failed" if failing else "passed",
        "detail": VP.format_text("skills/" + plan.name, findings)})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **{NESTED_ENV: "1"})
    suite = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                           cwd=plan.workdir, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=900)
    result.checks.append({"name": "repository tests",
                          "status": "passed" if suite.returncode == 0 else "failed",
                          "detail": tail(suite.stderr + suite.stdout)})
    claude = shutil.which("claude")
    if not plugin_validate or not claude:
        result.checks.append({"name": "plugin validation", "status": "skipped",
                              "detail": "run: claude plugin validate --strict ." if not claude
                              else "skipped by --skip-plugin-validate"})
        return
    outputs, code = [], 0
    for target in (".", os.path.join(".claude-plugin", "plugin.json")):
        run = subprocess.run([claude, "plugin", "validate", "--strict", target], cwd=plan.workdir,
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=300)
        outputs.append(tail(run.stdout + run.stderr, 10))
        code = code or run.returncode
    result.checks.append({"name": "plugin validation", "status": "passed" if code == 0 else "failed",
                          "detail": "\n".join(outputs)})


def apply_import(plan, run_checks=True, plugin_validate=True):
    """Create the branch, copy the approved files, and run checks. Never commits."""
    result = Result(plan=plan)
    if not plan.ok:
        result.problems.append("plan has refusals; nothing was changed")
        return result
    if plan.worktree:
        made = git(plan.dest, "worktree", "add", "-b", plan.branch, plan.worktree, "HEAD")
    else:
        made = git(plan.dest, "switch", "-c", plan.branch)
    if made.returncode != 0:
        result.problems.append("could not create branch %s: %s" % (plan.branch, tail(made.stderr, 5)))
        return result
    try:
        copy_files(plan, result)
    except (OSError, ValueError) as exc:
        result.problems.append(str(exc))
        return result
    result.applied = True
    if VP.compute_digest(plan.target) != plan.digest:
        result.problems.append("imported files do not match the approved digest")
    if run_checks:
        run_post_import_checks(plan, result, plugin_validate)
    return result


def next_steps(plan, result=None):
    where = plan.workdir or plan.dest
    steps = []
    if result is not None and result.applied:
        steps.append("Changes are not committed. Review them: git -C %s status && git -C %s diff" % (where, where))
        steps.append("Commit, push and open a pull request only when you decide to; this tool does none of them.")
    if not plan.publication_authorized:
        steps.append("Publication is not authorized: keep the branch local.")
    steps.append("Version and release metadata were not changed.")
    return steps


def format_plan(plan):
    lines = ["Import plan for %s" % (plan.name or "(unnamed candidate)"),
             "  candidate: %s" % plan.staging,
             "  destination: %s (current branch %s, %d uncommitted path(s))"
             % (plan.dest, plan.current_branch or "?", plan.dirty_paths)]
    if plan.worktree:
        lines.append("  worktree: %s" % plan.worktree)
    if plan.target:
        lines.append("  branch: %s" % plan.branch)
        lines.append("  target: %s" % plan.target)
        lines.extend("    + %s" % rel for rel in plan.files)
    lines.extend("  note: %s" % note for note in plan.notes)
    if plan.refusals:
        lines.append("Refused:")
        lines.extend("  - %s" % r for r in plan.refusals)
    return "\n".join(lines)


def format_result(result):
    lines = [format_plan(result.plan), ""]
    if result.applied:
        lines.append("Copied %d file(s) into %s" % (len(result.copied), result.plan.target))
    for check in result.checks:
        lines.append("Check %s: %s" % (check["name"], check["status"]))
        if check["status"] == "failed":
            lines.append("    " + check["detail"].replace("\n", "\n    "))
    lines.extend("Problem: %s" % p for p in result.problems)
    lines.extend("Next: %s" % s for s in next_steps(result.plan, result))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="import-portable-skill.py",
        description="Plan (default) or apply a local import of an approved candidate. Never commits or pushes.")
    parser.add_argument("staging", help="staging folder with manifest.json, REVIEW.md and skill/")
    parser.add_argument("--dest", required=True, help="root of the tobin-superpowers checkout")
    parser.add_argument("--apply", action="store_true", help="create the branch and copy files")
    parser.add_argument("--allow-overwrite", action="store_true",
                        help="replace an existing skills/<name>/ (only after the user approves)")
    parser.add_argument("--worktree", metavar="PATH", help="create the branch in a new git worktree at PATH")
    parser.add_argument("--branch", help="feature branch name (default promote-skill/<name>)")
    parser.add_argument("--skip-plugin-validate", action="store_true", help="do not run claude plugin validate")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    VP.tolerate_console_encoding()
    try:
        plan = plan_import(args.staging, args.dest, args.allow_overwrite, args.worktree, args.branch)
    except DestinationUnavailable:
        print("import-portable-skill: destination unavailable: %s\nThe candidate is kept at %s. "
              "When the checkout is available, re-run with --dest pointing at its root."
              % (args.dest, os.path.abspath(args.staging)), file=sys.stderr)
        return 2
    except OSError as exc:
        print("import-portable-skill: error: %s" % exc, file=sys.stderr)
        return 2
    result = apply_import(plan, plugin_validate=not args.skip_plugin_validate) if args.apply and plan.ok else None
    if args.json:
        data = {"ok": plan.ok if result is None else result.ok, "applied": bool(result and result.applied),
                "plan": asdict(plan), "copied": result.copied if result else [],
                "checks": result.checks if result else [], "problems": result.problems if result else [],
                "next_steps": next_steps(plan, result)}
        print(json.dumps(data, indent=2))
    elif result is None:
        print(format_plan(plan))
        if plan.ok:
            print("\nPlan only: nothing was changed. Re-run with --apply after the user confirms.")
    else:
        print(format_result(result))
    if not plan.ok:
        return 1
    return 0 if result is None or result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
