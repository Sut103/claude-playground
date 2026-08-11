#!/bin/bash
# Scripts read .claude/** relative to CWD; anchor to the project root so they
# work when invoked from a subdirectory (e.g. an epic worktree).
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
echo "Getting tasks..."
echo ""
echo ""

echo "🚫 Blocked Tasks"
echo "================"
echo ""

found=0

for epic_dir in .claude/epics/*/; do
  [ -d "$epic_dir" ] || continue
  epic_name=$(basename "$epic_dir")

  for task_file in "$epic_dir"/[0-9]*.md; do
    [ -f "$task_file" ] || continue
    # Task files are named <issue-number>.md. The [0-9]*.md glob also catches
    # CCPM's own <N>-analysis.md files, which would be counted as phantom tasks.
    case "$(basename "$task_file" .md)" in *[!0-9]*) continue ;; esac

    # Check if task is open
    status=$(grep "^status:" "$task_file" | head -1 | sed 's/^status: *//')
    if [ "$status" != "open" ] && [ -n "$status" ]; then
      continue
    fi

    # Check for dependencies
    deps_line=$(grep "^depends_on:" "$task_file" | head -1)
    if [ -n "$deps_line" ]; then
      deps=$(echo "$deps_line" | sed 's/^depends_on: *//' | sed 's/^\[//' | sed 's/\]$//' | sed 's/,/ /g' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
      [ -z "$deps" ] && deps=""
    else
      deps=""
    fi

    # Having a depends_on entry is not the same as being blocked — a task is
    # blocked only while some dependency is still unclosed. Reporting on the
    # mere presence of dependencies left tasks listed as blocked forever, even
    # after everything they waited on had closed.
    unmet=""
    for dep in $deps; do
      dep_file="$epic_dir$dep.md"
      if [ ! -f "$dep_file" ]; then
        unmet="$unmet #$dep(missing)"
        continue
      fi
      dep_status=$(grep "^status:" "$dep_file" | head -1 | sed 's/^status: *//')
      [ "$dep_status" = "closed" ] || unmet="$unmet #$dep"
    done

    if [ -n "$unmet" ]; then
      task_name=$(grep "^name:" "$task_file" | head -1 | sed 's/^name: *//')
      task_num=$(basename "$task_file" .md)

      echo "⏸️ Task #$task_num - $task_name"
      echo "   Epic: $epic_name"
      echo "   Blocked by: [$deps]"
      echo "   Waiting for:$unmet"
      echo ""
      ((found++))
    fi
  done
done

if [ $found -eq 0 ]; then
  echo "No blocked tasks found!"
  echo ""
  echo "💡 All tasks with dependencies are either completed or in progress."
else
  echo "📊 Total blocked: $found tasks"
fi

exit 0
