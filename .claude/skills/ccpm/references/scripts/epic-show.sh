#!/bin/bash

epic_name="$1"

if [ -z "$epic_name" ]; then
  echo "❌ Please provide an epic name"
  echo "Usage: bash epic-show.sh <epic-name>"
  exit 1
fi

echo "Getting epic..."
echo ""
echo ""

epic_dir=".claude/epics/$epic_name"
epic_file="$epic_dir/epic.md"

if [ ! -f "$epic_file" ]; then
  echo "❌ Epic not found: $epic_name"
  echo ""
  echo "Available epics:"
  for dir in .claude/epics/*/; do
    [ -d "$dir" ] && echo "  • $(basename "$dir")"
  done
  exit 1
fi

# Display epic details
echo "📚 Epic: $epic_name"
echo "================================"
echo ""

# Extract metadata
status=$(grep "^status:" "$epic_file" | head -1 | sed 's/^status: *//')
progress=$(grep "^progress:" "$epic_file" | head -1 | sed 's/^progress: *//')
github=$(grep "^github:" "$epic_file" | head -1 | sed 's/^github: *//')
# A parenthesized value is an unfilled template placeholder, not a URL — treat as unset
case "$github" in \(*) github="" ;; esac
created=$(grep "^created:" "$epic_file" | head -1 | sed 's/^created: *//')

echo "📊 Metadata:"
echo "  Status: ${status:-planning}"
echo "  Progress: ${progress:-0%}"
[ -n "$github" ] && echo "  GitHub: $github"
echo "  Created: ${created:-unknown}"
echo ""

# Show tasks
echo "📝 Tasks:"
task_count=0
open_count=0
closed_count=0

for task_file in "$epic_dir"/[0-9]*.md; do
  [ -f "$task_file" ] || continue

  task_num=$(basename "$task_file" .md)
  task_name=$(grep "^name:" "$task_file" | head -1 | sed 's/^name: *//')
  task_status=$(grep "^status:" "$task_file" | head -1 | sed 's/^status: *//')
  parallel=$(grep "^parallel:" "$task_file" | head -1 | sed 's/^parallel: *//')

  if [ "$task_status" = "closed" ] || [ "$task_status" = "completed" ]; then
    echo "  ✅ #$task_num - $task_name"
    ((closed_count++))
  else
    # Build the marker into the line. Emitting it after the echo above put it at
    # the start of the *next* task's line, so every marker read as belonging to
    # the wrong task.
    suffix=""
    [ "$parallel" = "true" ] && suffix=" (parallel)"
    echo "  ⬜ #$task_num - $task_name$suffix"
    ((open_count++))
  fi

  ((task_count++))
done

if [ $task_count -eq 0 ]; then
  echo "  No tasks created yet"
  echo "  Say: break down the $epic_name epic"
fi

echo ""
echo "📈 Statistics:"
echo "  Total tasks: $task_count"
echo "  Open: $open_count"
echo "  Closed: $closed_count"
[ $task_count -gt 0 ] && echo "  Completion: $((closed_count * 100 / task_count))%"

# Next actions
echo ""
echo "💡 Actions:"
[ $task_count -eq 0 ] && echo "  • Decompose into tasks — say: break down the $epic_name epic"
[ -z "$github" ] && [ $task_count -gt 0 ] && echo "  • Sync to GitHub — say: sync the $epic_name epic to GitHub"
[ -n "$github" ] && [ "$status" != "completed" ] && echo "  • Start work — say: start working on the $epic_name epic"

exit 0
