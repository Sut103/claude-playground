#!/bin/bash
# Print a markdown file's body with its YAML frontmatter removed.
#
# `sed '1,/^---$/d'` already consumes BOTH delimiters: the range starts at
# line 1 (the opening ---) and its end regex is searched from line 2, so it
# closes on the terminating ---. Chaining a second identical command — as
# CCPM's docs used to — re-opens a range on the first body line and, finding
# no further ---, deletes through EOF, leaving an empty body.
#
# Files without frontmatter are passed through untouched.
set -u
file="${1:?usage: strip-frontmatter.sh <file>}"
if [ "$(head -1 "$file")" = "---" ]; then
  sed '1,/^---$/d' "$file"
else
  cat "$file"
fi
