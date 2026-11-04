"""Report which standards rules a plan copies verbatim.

Usage: python3 -I check-coverage.py PLAN STANDARDS_DIR [STANDARDS_DIR ...]
A rule is a "- " bullet outside code fences. Whitespace and markdown emphasis are ignored.
Exit 0 if every rule is present, 1 if any is missing, 2 on bad usage.
"""
import pathlib, re, sys
from datetime import datetime

def norm(s):
    return re.sub(r"\s+", " ", s.replace("**", "").replace("`", "")).strip()

def rules(path):
    fenced = False
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("- "):
            yield line[2:].strip()

if len(sys.argv) < 3:
    sys.exit(__doc__)
plan = pathlib.Path(sys.argv[1]).expanduser()
dirs = [pathlib.Path(d).expanduser() for d in sys.argv[2:]]
text = norm(plan.read_text())
plan_mtime = plan.stat().st_mtime
hit = total = 0
for d in dirs:
    for f in sorted(d.glob("*.md")):
        rs = list(rules(f))
        missing = [r for r in rs if norm(r) not in text]
        newer = " (STANDARD NEWER THAN PLAN)" if f.stat().st_mtime > plan_mtime else ""
        print(f"{f.stem}: {len(rs) - len(missing)}/{len(rs)} verbatim{newer}")
        for r in missing:
            print(f"  MISSING: {r}")
        hit += len(rs) - len(missing)
        total += len(rs)
print(f"TOTAL: {hit}/{total} rules verbatim in {plan} (plan modified {datetime.fromtimestamp(plan_mtime):%Y-%m-%d})")
sys.exit(0 if hit == total else 1)
