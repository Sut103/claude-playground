# Conventions — File Formats, Paths & Rules

Read this before doing any file operations across all phases.

---

## Directory Structure

```
.claude/
├── prds/
│   └── <feature-name>.md          # Product requirement documents
├── epics/
│   ├── <feature-name>/
│   │   ├── epic.md                # Technical epic
│   │   ├── <N>.md                 # Task files (named by GitHub issue number after sync)
│   │   ├── <N>-analysis.md        # Parallel work stream analysis
│   │   ├── github-mapping.md      # Issue number → URL mapping
│   │   ├── execution-status.md    # Active agents tracker
│   │   └── updates/
│   │       └── <issue_N>/
│   │           ├── stream-A.md    # Per-agent progress
│   │           ├── progress.md    # Overall issue progress
│   │           └── execution.md  # Execution state
│   └── archived/
│       └── <feature-name>/        # Completed epics
└── context/                       # Project context docs (separate system)
```

---

## Frontmatter Schemas

### PRD (.claude/prds/<name>.md)
```yaml
---
name: <feature-name>        # kebab-case, matches filename
description: <one-liner>    # used in lists and summaries
status: backlog | active | completed
created: <ISO 8601>         # date -u +"%Y-%m-%dT%H:%M:%SZ"
---
```

### Epic (.claude/epics/<name>/epic.md)
```yaml
---
name: <feature-name>
status: backlog | in-progress | completed
created: <ISO 8601>
updated: <ISO 8601>
progress: 0%                # recalculated when tasks close
prd: .claude/prds/<name>.md
github: https://github.com/<owner>/<repo>/issues/<N>  # set on sync
---
```

### Task (.claude/epics/<name>/<N>.md)
```yaml
---
name: <Task Title>
status: open | in-progress | closed
created: <ISO 8601>
updated: <ISO 8601>
github: https://github.com/<owner>/<repo>/issues/<N>  # set on sync
depends_on: []              # issue numbers this must wait for
parallel: true              # can run concurrently with non-conflicting tasks
conflicts_with: []          # issue numbers that touch the same files
---
```

### Progress (.claude/epics/<name>/updates/<N>/progress.md)
```yaml
---
issue: <N>
started: <ISO 8601>
last_sync: <ISO 8601>
completion: 0%
---
```

---

## Datetime Rule

Always get real current datetime from the system — never use placeholder text:
```bash
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

---

## Frontmatter Update Pattern

When updating a single frontmatter field in an existing file:
```bash
sed -i.bak "/^<field>:/c\\<field>: <value>" <file>
rm <file>.bak
```

When stripping frontmatter to get body content for GitHub:
```bash
bash <skill>/references/scripts/strip-frontmatter.sh <file> > /tmp/body.md
```

Do **not** chain two `1,/^---$/d` ranges. A single one already removes both
delimiters — the range opens on line 1 and its end regex is searched from
line 2, so it closes on the terminating `---`. A second identical command
re-opens a range on the first body line, finds no further `---`, and deletes
through EOF, producing an empty body.

---

## GitHub Operations

### Repository Safety Check (run before any write operation)
```bash
remote_url=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$remote_url" == *"automazeio/ccpm"* ]]; then
  echo "❌ Cannot write to the CCPM template repository."
  echo "Update remote: git remote set-url origin https://github.com/YOUR/REPO.git"
  exit 1
fi
REPO=$(echo "$remote_url" | sed 's|.*github.com[:/]||' | sed 's|\.git$||')
```

### Authentication
Don't pre-check authentication. Run the `gh` command and handle failure:
```bash
gh <command> || echo "❌ GitHub CLI failed. Run: gh auth login"
```

### Transport: REST only (`gh api`)

This environment serves the GitHub REST API but blocks GraphQL. Every
`gh issue` / `gh label` / `gh repo` porcelain subcommand issues a GraphQL
request (`gh issue create` sends a `RepositoryInfo` preamble even though the
create itself is REST), so they all fail with HTTP 403 here.

**Use `gh api` for all GitHub operations.** Equivalents:

| Porcelain (blocked) | REST via `gh api` |
|---|---|
| `gh issue create` | `gh api --method POST repos/$REPO/issues --input <json>` |
| `gh issue view <N> --json ...` | `gh api repos/$REPO/issues/<N> --jq '...'` |
| `gh issue list` | `gh api "repos/$REPO/issues?state=all&per_page=100"` |
| `gh issue comment <N>` | `gh api --method POST repos/$REPO/issues/<N>/comments --input <json>` |
| `gh issue close <N>` | `gh api --method PATCH repos/$REPO/issues/<N> --input <json>` |
| `gh issue edit <N> --body-file` | `gh api --method PATCH repos/$REPO/issues/<N> --input <json>` |
| `gh issue edit <N> --add-label` | `gh api --method POST repos/$REPO/issues/<N>/labels --input <json>` |
| `gh issue edit <N> --add-assignee` | `gh api --method POST repos/$REPO/issues/<N>/assignees --input <json>` |
| `gh label create` | `gh api --method POST repos/$REPO/labels --input <json>` |
| `gh label list` | `gh api repos/$REPO/labels --jq '.[].name'` |
| `gh repo view` (existence check) | `gh api repos/$REPO --jq .full_name` |
| `gh sub-issue create --parent` | `gh api --method POST repos/$REPO/issues/<parent>/sub_issues -F sub_issue_id=<child_id>` |

Build JSON bodies with `jq -n` rather than string interpolation, so titles and
bodies containing quotes, backticks or newlines survive intact:
```bash
jq -n --arg t "$title" --rawfile b /tmp/body.md --argjson l '["task"]' \
  '{title:$t, body:$b, labels:$l}' > /tmp/payload.json
gh api --method POST "repos/$REPO/issues" --input /tmp/payload.json --jq .number
```

**Sub-issues take the child's internal `id`, not its issue number:**
```bash
child_id=$(gh api "repos/$REPO/issues/<N>" --jq .id)
```

### Getting Issue Numbers
```bash
# From a task file's github field:
grep 'github:' <file> | grep -oE '[0-9]+$'
```

---

## Git / Worktree Conventions

- One branch per epic: `epic/<name>`
- Worktrees live at `../epic-<name>/` (sibling to project root)
- Always start branches from an up-to-date main:
  ```bash
  git checkout main && git pull origin main
  git worktree add ../epic-<name> -b epic/<name>
  ```
- Commit format inside epics: `Issue #<N>: <description>`
- Never use `--force` in any git operation

---

## Naming Conventions

- Feature names: kebab-case, lowercase, letters/numbers/hyphens, starts with a letter
- Task files before sync: `001.md`, `002.md`, ... (sequential)
- Task files after sync: renamed to GitHub issue number (e.g., `1234.md`)
- Labels applied on sync: `epic`, `epic:<name>`, `feature` (for epics); `task`, `epic:<name>` (for tasks)

---

## Epic Progress Calculation

```bash
# `! -name "*[!0-9]*.md"` keeps <N>-analysis.md out of the count — it lives in
# the same directory and would otherwise inflate the denominator, holding
# progress permanently below its true value.
tasks=$(find .claude/epics/<name> -maxdepth 1 -name "[0-9]*.md" ! -name "*[!0-9]*.md")
total=$(echo "$tasks" | grep -c .)
closed=$(echo "$tasks" | xargs grep -l '^status: closed' 2>/dev/null | wc -l)
progress=$((closed * 100 / total))
```

Update epic frontmatter when any task closes.
