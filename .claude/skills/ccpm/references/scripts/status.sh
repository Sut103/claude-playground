#!/bin/bash

echo "Getting status..."
echo ""
echo ""


echo "📊 Project Status"
echo "================"
echo ""

echo "📄 PRDs:"
if [ -d ".claude/prds" ]; then
  total=$(ls .claude/prds/*.md 2>/dev/null | wc -l)
  echo "  Total: $total"
else
  echo "  No PRDs found"
fi

echo ""
echo "📚 Epics:"
if [ -d ".claude/epics" ]; then
  total=$(ls -d .claude/epics/*/ 2>/dev/null | grep -v '/archived/$' | wc -l)
  echo "  Total: $total"
else
  echo "  No epics found"
fi

echo ""
echo "📝 Tasks:"
if [ -d ".claude/epics" ]; then
  task_files=$(find .claude/epics -path "*/archived/*" -prune -o -name "[0-9]*.md" -print 2>/dev/null)
  total=$(printf '%s\n' "$task_files" | grep -c . )
  open=$(printf '%s\n' "$task_files" | grep . | xargs -r grep -l "^status: *open" 2>/dev/null | wc -l)
  in_progress=$(printf '%s\n' "$task_files" | grep . | xargs -r grep -l "^status: *in-progress" 2>/dev/null | wc -l)
  closed=$(printf '%s\n' "$task_files" | grep . | xargs -r grep -l "^status: *\(closed\|completed\)" 2>/dev/null | wc -l)
  echo "  Open: $open"
  echo "  In Progress: $in_progress"
  echo "  Closed: $closed"
  echo "  Total: $total"
  # in-progress is a documented task status (conventions.md), so it must appear
  # in the breakdown — otherwise the buckets silently fail to sum to the total.
  accounted=$((open + in_progress + closed))
  [ "$accounted" -ne "$total" ] && echo "  ⚠️ $((total - accounted)) task(s) have an unrecognized status"
else
  echo "  No tasks found"
fi

exit 0
