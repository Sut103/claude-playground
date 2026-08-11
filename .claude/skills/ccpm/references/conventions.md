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
awk 'NR==1 && $0=="---" {infm=1; next} infm && $0=="---" {infm=0; next} !infm' <file> > /tmp/body.md
```

Do **not** use `sed '1,/^---$/d; 1,/^---$/d'`. One `1,/^---$/d` already removes
the whole frontmatter block — line 1 opens the range and the closing `---` ends
it. The second copy then deletes from the body's first line up to the next
`^---$`, and a body with no `---` line of its own leaves the range open to end
of file, so the entire body is discarded. That produces an empty GitHub issue
with no error.

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

### Getting Issue Numbers
```bash
# From a task file's github field:
issue_number=$(grep '^github:' <file> | head -1 | grep -oE '[0-9]+$')
```

Before sync the `github:` field is empty, so this yields an empty string. Always
check before using it as an issue number — an empty value passed to `gh` targets
the wrong thing or fails obscurely:
```bash
if [ -z "$issue_number" ]; then
  echo "❌ <file> has no GitHub issue yet. Sync the epic first."
  exit 1
fi
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
total=$(ls .claude/epics/<name>/[0-9]*.md 2>/dev/null | wc -l)
closed=$(grep -l '^status: closed' .claude/epics/<name>/[0-9]*.md 2>/dev/null | wc -l)
progress=$((closed * 100 / total))
```

Update epic frontmatter when any task closes.
