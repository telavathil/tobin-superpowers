#!/usr/bin/env bash
# Wrap superpowers' task-brief so a plan's Global Constraints travel with the
# task text.
#
# Under subagent-driven development an implementer reads only its brief, never
# the plan. Upstream task-brief prints the task section alone, so the code
# standards copied into Global Constraints never reach the implementer that
# plan-code.md wrote them for.
#
# Usage: task-brief.sh PLAN_FILE TASK_NUMBER [OUTFILE]
# Arguments and output path are upstream's; this only prepends.
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "usage: $(basename "$0") PLAN_FILE TASK_NUMBER [OUTFILE]" >&2
  exit 2
fi

plan=$1
task=$2

# Several marketplaces can cache their own copy. Sort on the version segment
# alone: sorting whole paths ranks the marketplace directory name ahead of the
# version and can select an older copy from a disabled plugin.
upstream=$(
  find "$HOME/.claude/plugins/cache" \
    -path '*/superpowers/*/skills/subagent-driven-development/scripts/task-brief' \
    -type f 2>/dev/null |
    while IFS= read -r path; do
      version=${path#*/superpowers/}
      printf '%s\t%s\n' "${version%%/*}" "$path"
    done | sort -V | tail -1 | cut -f2
)

if [ -z "$upstream" ]; then
  echo "superpowers task-brief not found under ~/.claude/plugins/cache" >&2
  exit 3
fi

result=$("${BASH:-bash}" "$upstream" "$@")
out=${result#wrote }
out=${out%%:*}

# A task number prefix-matches a longer task name: "3" also selects "3G".
headings=$(grep -c '^#\{1,\}[[:space:]]\{1,\}Task[[:space:]]' "$out" || true)
if [ "$headings" -gt 1 ]; then
  echo "warning: brief holds $headings task headings; '$task' prefix-matched a longer name" >&2
fi

constraints=$(
  awk '
    /^```/ { infence = !infence }
    !infence && /^## / { inside = ($0 ~ /^## Global Constraints[[:space:]]*$/) }
    inside { print }
  ' "$plan"
)

if [ -z "$constraints" ]; then
  echo "$result (no Global Constraints section in $plan)" >&2
  exit 0
fi

{
  printf '%s\n' "$constraints"
  printf -- '\n---\n\n'
  cat "$out"
} > "$out.tmp"
mv "$out.tmp" "$out"

echo "$result + Global Constraints: $(wc -l < "$out" | tr -d ' ') lines"
