# Sync — Push to GitHub & Track Progress

This phase covers pushing local epics/tasks to GitHub as issues, syncing progress as comments, and closing issues when work is done.

---

## Repository Safety Check

**Always run this before any GitHub write operation:**

```bash
remote_url=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$remote_url" == *"automazeio/ccpm"* ]]; then
  echo "❌ Cannot sync to the CCPM template repository."
  echo "Update remote: git remote set-url origin https://github.com/YOUR/REPO.git"
  exit 1
fi
REPO=$(echo "$remote_url" | sed 's|.*github.com[:/]||' | sed 's|\.git$||')
```

---

## Epic Sync — Push Epic + Tasks to GitHub

**Trigger**: User wants to push a local epic and its tasks to GitHub as issues.

### Preflight
- Verify `.claude/epics/<name>/epic.md` exists.
- Verify numbered task files exist — if none: "❌ No tasks to sync. Decompose the epic first."

### Process

**Step 1 — Create epic issue:**

Strip frontmatter from epic.md (see `conventions.md` — the awk form, not a
doubled `sed`, which silently empties the body), then create the issue over the
REST API so the response carries the new issue number:

```bash
strip_frontmatter() {
  awk 'NR==1 && $0=="---" {infm=1; next} infm && $0=="---" {infm=0; next} !infm' "$1"
}

strip_frontmatter .claude/epics/<name>/epic.md > /tmp/epic-body.md

jq -n --arg t "Epic: <name>" --rawfile b /tmp/epic-body.md \
  '{title: $t, body: $b, labels: ["epic", "epic:<name>", "feature"]}' > /tmp/epic-payload.json

epic_number=$(gh api -X POST "repos/$REPO/issues" \
  --input /tmp/epic-payload.json --jq '.number')
```

**Verify the body landed** — an empty body is the failure this step is most
prone to, and GitHub accepts it without complaint:
```bash
[ -s /tmp/epic-body.md ] || { echo "❌ Epic body is empty — check frontmatter stripping"; exit 1; }
```

Do **not** use `gh issue create --json number -q .number`: `gh issue create` has
no `--json` flag (it fails with `unknown flag: --json`), and it talks to the
GraphQL API, which is unavailable in some environments. `gh api` is REST and
returns the created issue as JSON.

**Step 2 — Create task sub-issues:**

Check if `gh-sub-issue` extension is available:
```bash
if gh extension list | grep -q "yahsan2/gh-sub-issue"; then
  use_subissues=true
fi
```

For <5 tasks: create sequentially.
For ≥5 tasks: use parallel Task agents (3-4 tasks per batch).

Per task:
```bash
strip_frontmatter <task_file> > /tmp/task-body.md
[ -s /tmp/task-body.md ] || { echo "❌ Task body is empty"; exit 1; }

jq -n --arg t "<task_name>" --rawfile b /tmp/task-body.md \
  '{title: $t, body: $b, labels: ["task", "epic:<name>"]}' > /tmp/task-payload.json

task_number=$(gh api -X POST "repos/$REPO/issues" \
  --input /tmp/task-payload.json --jq '.number')
```

**Linking tasks to the epic.** If `gh-sub-issue` is installed, use it:
```bash
gh sub-issue add --parent "$epic_number" --child "$task_number"
```

Otherwise link over REST — GitHub's sub-issues API accepts the child's internal
`id` (not its issue number):
```bash
child_id=$(gh api "repos/$REPO/issues/$task_number" --jq '.id')
gh api -X POST "repos/$REPO/issues/$epic_number/sub_issues" -F sub_issue_id="$child_id"
```

If neither works, fall back to a task list in the epic body (`- [ ] #<N>` lines),
which is what the "Closing an Issue" step below ticks off.

**Step 3 — Rename task files and update references:**

After all issues are created, rename `001.md` → `<issue_number>.md` and update the
`depends_on` / `conflicts_with` arrays to use real issue numbers.

**Rewrite only those two frontmatter lines — never the whole file.** A global
`sed "s/\b001\b/40/g"` corrupts prose, because `\b` treats a comma as a word
boundary: `2,001 segments` becomes `2,40 segments`, and `10,001 matches` becomes
`10,40 matches`. Any thousands-separated number ending in a task number is
silently rewritten.

```bash
# mapping.tsv holds one "<seq>\t<issue_number>" row per task, in creation order.
remap_field() {   # remap_field <file> <field>
  file="$1"; field="$2"
  line=$(grep "^$field:" "$file" | head -1) || return 0
  [ -z "$line" ] && return 0
  values=$(printf '%s' "$line" | sed "s/^$field: *\[//" | sed 's/\]$//')
  [ -z "$values" ] && return 0

  out=""
  for v in $(printf '%s' "$values" | tr ',' ' '); do
    new=$(awk -F'\t' -v s="$v" '$1==s {print $2}' mapping.tsv)
    [ -z "$new" ] && new="$v"        # leave anything unmapped untouched
    out="$out, $new"
  done
  sed -i.bak "/^$field:/c\\$field: [${out#, }]" "$file" && rm "$file.bak"
}

while IFS=$'\t' read -r seq issue _; do
  remap_field "$seq.md" depends_on
  remap_field "$seq.md" conflicts_with
done < mapping.tsv

# Rename only after every file has been remapped, so the sequential names in
# mapping.tsv still resolve while remapping is in progress.
while IFS=$'\t' read -r seq issue _; do
  mv "$seq.md" "$issue.md"
done < mapping.tsv
```

Task bodies that mention `001`-style numbers in prose keep them — those bodies
are already on GitHub as issue text, and `github-mapping.md` (Step 6) is what
resolves a sequential number to its issue number.

**Step 3b — Rewrite the epic's task checklist to issue numbers:**

`structure.md` writes the checklist as `- [ ] 001.md - <title> (parallel: …)`, but
"Closing an Issue" below ticks items off by matching `- [ ] #<N>`. Convert the
list during sync, in `epic.md` and in the epic issue body, or nothing will ever
get ticked:

```bash
while IFS=$'\t' read -r seq issue title; do
  sed -i.bak "s|^- \[ \] $seq\.md - |- [ ] #$issue - |" .claude/epics/<name>/epic.md
done < mapping.tsv
rm -f .claude/epics/<name>/epic.md.bak

# Push the same body to the epic issue so local and GitHub agree
strip_frontmatter .claude/epics/<name>/epic.md > /tmp/epic-body.md
jq -n --rawfile b /tmp/epic-body.md '{body: $b}' > /tmp/epic-patch.json
gh api -X PATCH "repos/$REPO/issues/$epic_number" --input /tmp/epic-patch.json --jq '.number'
```

**Step 4 — Update frontmatter:**
```bash
current_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Update github: and updated: fields in epic.md and each task file
github_url="https://github.com/$REPO/issues/<number>"
sed -i.bak "/^github:/c\\github: $github_url" <file>
sed -i.bak "/^updated:/c\\updated: $current_date" <file>
rm <file>.bak
```

**Step 5 — Create worktree for the epic:**
```bash
git checkout main && git pull origin main
git worktree add ../epic-<name> -b epic/<name>
```

**Step 6 — Create github-mapping.md:**
```markdown
# GitHub Issue Mapping
Epic: #<N> - https://github.com/<repo>/issues/<N>
Tasks:
- #<N>: <title> - https://github.com/<repo>/issues/<N>
Synced: <datetime>
```

**Output:**
```
✅ Synced epic <name> to GitHub
  Epic: #<N>
  Tasks: N sub-issues
  Worktree: ../epic-<name>
  Next: "start working on issue <N>" or "start the <name> epic"
```

---

## Issue Sync — Post Progress to GitHub

**Trigger**: User wants to sync local development progress to a GitHub issue as a comment.

### Preflight
- Verify issue exists: `gh issue view <N> --json state`
- Check `.claude/epics/*/updates/<N>/` exists with a `progress.md` file.
- Check `last_sync` in progress.md — if synced <5 minutes ago, confirm before proceeding.

### Process

Gather updates from `.claude/epics/<epic>/updates/<N>/` (progress.md, notes.md, commits.md).

Format and post a comment:
```bash
gh issue comment <N> --body-file /tmp/update-comment.md
```

Comment format:
```markdown
## 🔄 Progress Update - <date>

### ✅ Completed Work
### 🔄 In Progress
### 📝 Technical Notes
### 📊 Acceptance Criteria Status
### 🚀 Next Steps
### ⚠️ Blockers

---
*Progress: N% | Synced at <timestamp>*
```

After posting: update `last_sync` in progress.md frontmatter, update `updated` in the task file.

Add sync marker to local files to prevent duplicate comments:
```markdown
<!-- SYNCED: <datetime> -->
```

---

## Closing an Issue

**Trigger**: User marks a task complete.

### Process

1. Find the local task file (`.claude/epics/*/<N>.md`).
2. Update frontmatter: `status: closed`, `updated: <now>`.
3. Post completion comment:
```bash
echo "✅ Task completed — all acceptance criteria met." | gh issue comment <N> --body-file -
gh issue close <N>
```
4. Check off the task in the epic issue body:
```bash
gh issue view <epic_N> --json body -q .body > /tmp/epic-body.md
sed -i "s/- \[ \] #<N>/- [x] #<N>/" /tmp/epic-body.md
gh issue edit <epic_N> --body-file /tmp/epic-body.md
```
5. Recalculate and update epic progress: `progress = closed_tasks / total_tasks * 100`

---

## Merging an Epic

**Trigger**: User wants to merge a completed epic back to main.

### Preflight
- Verify worktree `../epic-<name>` exists.
- Check for uncommitted changes in the worktree — block if dirty.
- Warn if any task issues are still open.

### Process

```bash
# From worktree: run project tests if detectable
cd ../epic-<name>
# detect and run: npm test / pytest / cargo test / go test / etc.

# From main repo:
git checkout main && git pull origin main
git merge epic/<name> --no-ff -m "Merge epic: <name>"
git push origin main

# Cleanup
git worktree remove ../epic-<name>
git branch -d epic/<name>
git push origin --delete epic/<name>

# Archive
mkdir -p .claude/epics/archived/
mv .claude/epics/<name> .claude/epics/archived/

# Close GitHub issues
epic_issue=$(grep 'github:' .claude/epics/archived/<name>/epic.md | grep -oE '[0-9]+$')
gh issue close $epic_issue -c "Epic completed and merged to main"
```

Update epic.md frontmatter: `status: completed`.

---

## Reporting a Bug Against a Completed Issue

**Trigger**: User finds a bug while testing a completed or in-progress issue — e.g. "found a bug in issue 42", "email validation is broken, came up while testing issue 42".

The workflow should stay automated: create a linked bug task without losing context from the original issue.

### Process

**Step 1 — Read the original issue for context:**
```bash
gh issue view <original_N> --json title,body,labels
```
Also read the local task file if it exists: `.claude/epics/*/<original_N>.md`

**Step 2 — Create a local bug task file:**

```markdown
---
name: Bug: <short description>
status: open
created: <run: date -u +"%Y-%m-%dT%H:%M:%SZ">
updated: <same>
github:
depends_on: []
parallel: false
conflicts_with: []
bug_for: <original_N>
---

# Bug: <short description>

## Context
Found while working on / testing issue #<original_N>: <original title>

## Description
<what's broken>

## Steps to Reproduce
<steps>

## Expected vs Actual
- Expected: 
- Actual: 

## Acceptance Criteria
- [ ] Bug is fixed
- [ ] Original issue #<original_N> behaviour is unaffected

## Effort Estimate
- Size: XS/S
```

Save to `.claude/epics/<same_epic_as_original>/bug-<original_N>-<slug>.md`

**Step 3 — Create a linked GitHub issue:**
```bash
gh issue create \
  --repo "$REPO" \
  --title "Bug: <short description>" \
  --body "$(cat /tmp/bug-body.md)" \
  --label "bug,epic:<epic_name>" \
  --json number -q .number
```

The issue body should open with `Fixes / follow-up to #<original_N>` so GitHub auto-links them.

**Step 4 — Update the local file** with the GitHub issue number and rename to `<new_N>.md`.

**Output:**
```
✅ Bug issue created: #<new_N> — "Bug: <short description>"
  Linked to: #<original_N>
  Epic: <epic_name>

Start fixing it: "start working on issue <new_N>"
```
