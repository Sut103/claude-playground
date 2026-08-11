#!/bin/bash
# Scripts read .claude/** relative to CWD; anchor to the project root so they
# work when invoked from a subdirectory (e.g. an epic worktree).
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
echo "Getting status..."
echo ""
echo ""

echo "📋 Next Available Tasks"
echo "======================="
echo ""

# Find tasks that are open and have no dependencies or whose dependencies are closed
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

    # Check dependencies
    deps_line=$(grep "^depends_on:" "$task_file" | head -1)
    if [ -n "$deps_line" ]; then
      deps=$(echo "$deps_line" | sed 's/^depends_on: *//' | sed 's/^\[//' | sed 's/\]$//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
      [ -z "$deps" ] && deps=""
    else
      deps=""
    fi

    # A task is available when it has no dependencies, or when every dependency
    # is closed. Only the first half used to be implemented, so once the
    # dependency-free tasks were done this script reported "no available tasks"
    # forever, no matter how much of the epic was actually unblocked.
    unmet=""
    if [ -n "$deps" ] && [ "$deps" != "depends_on:" ]; then
      for dep in $(echo "$deps" | tr ',' ' '); do
        dep_file="$epic_dir/$dep.md"
        if [ ! -f "$dep_file" ]; then
          unmet="$unmet $dep"
          continue
        fi
        dep_status=$(grep "^status:" "$dep_file" | head -1 | sed 's/^status: *//')
        [ "$dep_status" = "closed" ] || unmet="$unmet $dep"
      done
    fi

    if [ -z "$unmet" ]; then
      task_name=$(grep "^name:" "$task_file" | head -1 | sed 's/^name: *//')
      task_num=$(basename "$task_file" .md)
      parallel=$(grep "^parallel:" "$task_file" | head -1 | sed 's/^parallel: *//')

      echo "✅ Ready: #$task_num - $task_name"
      echo "   Epic: $epic_name"
      [ "$parallel" = "true" ] && echo "   🔄 Can run in parallel"
      echo ""
      ((found++))
    fi
  done
done

if [ $found -eq 0 ]; then
  echo "No available tasks found."
  echo ""
  echo "💡 Suggestions:"
  echo "  • Check blocked tasks: /pm:blocked"
  echo "  • View all tasks: /pm:epic-list"
fi

echo ""
echo "📊 Summary: $found tasks ready to start"

exit 0
