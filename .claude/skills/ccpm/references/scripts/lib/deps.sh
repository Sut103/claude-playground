#!/bin/bash
# Shared dependency resolution for the CCPM tracking scripts.
#
# A task's `depends_on` lists other task numbers in the same epic. A dependency
# is *met* once that task's status is closed (or completed). Tracking scripts
# must distinguish "has dependencies" from "has unmet dependencies" — otherwise
# every task with a `depends_on` entry stays blocked forever, even after its
# prerequisites close.
#
# ccpm_unmet_deps <task_file>
#   Prints the space-separated dependency numbers that are NOT yet closed.
#   Empty output means the task is ready to start.
#   A dependency whose file is missing counts as unmet — it can never be
#   satisfied, so reporting it as blocking surfaces the broken reference.
ccpm_unmet_deps() {
  task_file="$1"
  epic_dir=$(dirname "$task_file")

  deps_line=$(grep "^depends_on:" "$task_file" | head -1)
  [ -z "$deps_line" ] && return 0

  deps=$(printf '%s' "$deps_line" \
    | sed 's/^depends_on: *//' \
    | sed 's/^\[//' \
    | sed 's/\]$//' \
    | sed 's/,/ /g' \
    | tr -d "\"'")

  unmet=""
  for dep in $deps; do
    dep_file="$epic_dir/$dep.md"
    if [ ! -f "$dep_file" ]; then
      unmet="$unmet $dep"
      continue
    fi
    dep_status=$(grep "^status:" "$dep_file" | head -1 | sed 's/^status: *//')
    case "$dep_status" in
      closed|completed) ;;
      *) unmet="$unmet $dep" ;;
    esac
  done

  printf '%s' "${unmet# }"
}

# ccpm_declared_deps <task_file>
#   Prints every declared dependency, met or not. Used for display when a task
#   is reported as blocked.
ccpm_declared_deps() {
  deps_line=$(grep "^depends_on:" "$1" | head -1)
  [ -z "$deps_line" ] && return 0
  printf '%s' "$deps_line" \
    | sed 's/^depends_on: *//' \
    | sed 's/^\[//' \
    | sed 's/\]$//' \
    | sed 's/,/ /g' \
    | tr -d "\"'" \
    | sed 's/^[[:space:]]*//' \
    | sed 's/[[:space:]]*$//'
}
