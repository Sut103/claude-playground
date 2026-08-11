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

Strip frontmatter from epic.md, then:
```bash
bash <skill>/references/scripts/strip-frontmatter.sh .claude/epics/<name>/epic.md > /tmp/epic-body.md
jq -n --arg t "Epic: <name>" --rawfile b /tmp/epic-body.md \
      --argjson l '["epic","epic:<name>","feature"]' \
      '{title:$t, body:$b, labels:$l}' > /tmp/epic-payload.json
epic_number=$(gh api --method POST "repos/$REPO/issues" \
  --input /tmp/epic-payload.json --jq .number)
```

> `gh issue create` is unusable here: it has no `--json` flag, and it sends a
> GraphQL `RepositoryInfo` preamble that this environment blocks. Create issues
> through the REST endpoint as above. See `conventions.md` → *Transport*.

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
bash <skill>/references/scripts/strip-frontmatter.sh <task_file> > /tmp/task-body.md
jq -n --arg t "<task_name>" --rawfile b /tmp/task-body.md \
      --argjson l '["task","epic:<name>"]' \
      '{title:$t, body:$b, labels:$l}' > /tmp/task-payload.json
task_number=$(gh api --method POST "repos/$REPO/issues" \
  --input /tmp/task-payload.json --jq .number)
```

**Sub-issue linking (REST):**

`gh-sub-issue` is GraphQL-only, so it cannot run here. Link the parent/child
relationship through the REST sub-issues API instead — it takes the child's
internal `id`, not its issue number:

```bash
child_id=$(gh api "repos/$REPO/issues/$task_number" --jq .id)
gh api --method POST "repos/$REPO/issues/$epic_number/sub_issues" \
  -F sub_issue_id="$child_id" --jq .number
```

If that call fails, fall back to CCPM's plain mode: no parent/child link, and
the epic body carries a `- [ ] #<N>` checklist of its tasks.

**Step 3 — Rename task files and update references:**

After all issues are created, rename `001.md` → `<issue_number>.md` and update all `depends_on`/`conflicts_with` arrays to use real issue numbers (not sequential numbers).

```bash
# Build old→new mapping, then for each task file:
sed -i.bak "s/\b001\b/<new_num_1>/g" <file>  # repeat for each mapping
mv 001.md <new_num>.md
```

**Step 3b — Rewrite the epic body's task checklist and push it:**

The epic issue was created before the task issues existed, so its `## Tasks
Created` section still lists sequential filenames. Rewrite those entries to
`- [ ] #<issue_number> - <title>` in `epic.md`, then PATCH the epic issue with
the updated body.

Do not skip this. *Closing an Issue* below checks a task off with
`sed "s/- \[ \] #<N>/- [x] #<N>/"` against the epic body — if the body never
gained a `- [ ] #<N>` checklist, that substitution silently matches nothing
and epic progress never reflects closed tasks.

```bash
bash <skill>/references/scripts/strip-frontmatter.sh .claude/epics/<name>/epic.md > /tmp/epic-body.md
jq -n --rawfile b /tmp/epic-body.md '{body:$b}' > /tmp/epic-edit.json
gh api --method PATCH "repos/$REPO/issues/$epic_number" --input /tmp/epic-edit.json --jq .number
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
- Verify issue exists: `gh api repos/$REPO/issues/<N> --jq .state`
- Check `.claude/epics/*/updates/<N>/` exists with a `progress.md` file.
- Check `last_sync` in progress.md — if synced <5 minutes ago, confirm before proceeding.

### Process

Gather updates from `.claude/epics/<epic>/updates/<N>/` (progress.md, notes.md, commits.md).

Format and post a comment:
```bash
jq -n --rawfile b /tmp/update-comment.md '{body:$b}' > /tmp/comment.json
gh api --method POST "repos/$REPO/issues/<N>/comments" --input /tmp/comment.json --jq .id
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
jq -n '{body:"✅ Task completed — all acceptance criteria met."}' > /tmp/done.json
gh api --method POST "repos/$REPO/issues/<N>/comments" --input /tmp/done.json --jq .id
jq -n '{state:"closed", state_reason:"completed"}' > /tmp/close.json
gh api --method PATCH "repos/$REPO/issues/<N>" --input /tmp/close.json --jq .state
```
4. Check off the task in the epic issue body:
```bash
gh api "repos/$REPO/issues/<epic_N>" --jq .body > /tmp/epic-body.md
sed -i "s/- \[ \] #<N>/- [x] #<N>/" /tmp/epic-body.md
jq -n --rawfile b /tmp/epic-body.md '{body:$b}' > /tmp/epic-edit.json
gh api --method PATCH "repos/$REPO/issues/<epic_N>" --input /tmp/epic-edit.json --jq .number
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
jq -n '{body:"Epic completed and merged to main"}' > /tmp/epic-done.json
gh api --method POST "repos/$REPO/issues/$epic_issue/comments" --input /tmp/epic-done.json --jq .id
jq -n '{state:"closed", state_reason:"completed"}' > /tmp/close.json
gh api --method PATCH "repos/$REPO/issues/$epic_issue" --input /tmp/close.json --jq .state
```

Update epic.md frontmatter: `status: completed`.

---

## Reporting a Bug Against a Completed Issue

**Trigger**: User finds a bug while testing a completed or in-progress issue — e.g. "found a bug in issue 42", "email validation is broken, came up while testing issue 42".

The workflow should stay automated: create a linked bug task without losing context from the original issue.

### Process

**Step 1 — Read the original issue for context:**
```bash
gh api "repos/$REPO/issues/<original_N>" --jq '{title,body,labels:[.labels[].name]}'
```
Also read the local task file if it exists: `.claude/epics/*/<original_N>.md`

**Step 2 — Create a local bug task file:**

```markdown
---
name: Bug: <short description>
status: open
created: <run: date -u +"%Y-%m-%dT%H:%M:%SZ">
updated: <same>
github: (will be set on sync)
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
jq -n --arg t "Bug: <short description>" --rawfile b /tmp/bug-body.md \
      --argjson l '["bug","epic:<epic_name>"]' \
      '{title:$t, body:$b, labels:$l}' > /tmp/bug-payload.json
bug_number=$(gh api --method POST "repos/$REPO/issues" \
  --input /tmp/bug-payload.json --jq .number)
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
