"""Shared helpers for the promote-skill tests (not a test module).

Credential-like strings are generated here at runtime so that no secret-looking
literal is ever stored in the repository.
"""

import hashlib
import importlib.util
import json
import os
import random
import shutil
import string
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures", "promote")
SOURCE_SKILL = os.path.join(FIXTURES, "source", "diagram-as-code")
PERSONAL_DESCRIPTION = os.path.join(FIXTURES, "personal", "description.md")
CANDIDATE = os.path.join(FIXTURES, "candidate", "skill-promotion")
VALIDATOR = os.path.join(SCRIPTS, "validate-portable-skill.py")
IMPORTER = os.path.join(SCRIPTS, "import-portable-skill.py")

GIT_IDENTITY = ["-c", "user.name=Promote Test", "-c", "user.email=promote@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]


def load_script(module_name, path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_secrets(seed=7):
    """Credential-shaped values built at runtime, keyed by kind."""
    rng = random.Random(seed)

    def pick(alphabet, n):
        return "".join(rng.choice(alphabet) for _ in range(n))

    upper_digits = string.ascii_uppercase + string.digits
    alnum = string.ascii_letters + string.digits
    return {
        "aws": "AK" + "IA" + pick(upper_digits, 16),
        "github": "gh" + "p_" + pick(alnum, 36),
        "assignment": "api_key" + " = " + "'" + pick(alnum, 24) + "'",
        "private_key": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
    }


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_json(path):
    return json.loads(read(path))


def write_json(path, data):
    write(path, json.dumps(data, indent=2) + "\n")


def copy_candidate(parent, name="skill-promotion"):
    staging = os.path.join(parent, name)
    shutil.copytree(CANDIDATE, staging)
    return staging


def tree_hashes(root, skip=()):
    """Map relative path -> sha256 for every file under root."""
    result = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__"))
        for name in files:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if any(rel == s or rel.startswith(s + "/") for s in skip):
                continue
            with open(path, "rb") as handle:
                result[rel] = hashlib.sha256(handle.read()).hexdigest()
    return result


def approve(staging, validator, transfer=True, publication=False, status="approved"):
    """Record what the skill records after the user's explicit approval."""
    manifest_path = os.path.join(staging, "manifest.json")
    manifest = read_json(manifest_path)
    manifest["status"] = status
    manifest["approval"] = {
        "approved_by_user": status == "approved",
        "digest": validator.compute_digest(os.path.join(staging, "skill")) if status == "approved" else None,
        "transfer_authorized": transfer,
        "publication_authorized": publication,
    }
    write_json(manifest_path, manifest)
    review_path = os.path.join(staging, "REVIEW.md")
    review = read(review_path)
    head, _, _ = review.partition("## Approval")
    review_status = {"approved": "approved", "draft": "pending"}.get(status, status)
    write(review_path, head + "## Approval\n\nStatus: %s\nTransfer authorized: %s\n"
          "Publication authorized: %s\n" % (review_status, "yes" if transfer else "no",
                                           "yes" if publication else "no"))
    return manifest


def git(cwd, *args, check=True):
    return subprocess.run(["git", *GIT_IDENTITY, *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


BUILT_IN_SKILL_DIRS = {"hybrid-planning", "html-companion", "promote-skill", "shared"}


def _checkout_ignore(dirpath, names):
    skipped = {n for n in names if n in (".git", "__pycache__") or n.endswith(".pyc")}
    if os.path.normcase(os.path.abspath(dirpath)) == os.path.normcase(os.path.join(REPO_ROOT, "skills")):
        # Leave out skills promoted into this checkout, so every throwaway
        # checkout starts from the plugin's own skills only.
        skipped |= {n for n in names if n not in BUILT_IN_SKILL_DIRS}
    return skipped


def make_checkout(parent, name="checkout"):
    """A throwaway git checkout of this repository's working tree."""
    dest = os.path.join(parent, name)
    shutil.copytree(REPO_ROOT, dest, ignore=_checkout_ignore)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "baseline")
    return dest


def head_commit(cwd):
    return git(cwd, "rev-parse", "HEAD").stdout.strip()


def commit_count(cwd):
    return int(git(cwd, "rev-list", "--all", "--count").stdout.strip())
