# M0 — Reset & guardrails

Executable plan for milestone M0 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M0 closes the abandoned Plane-mirror PR run, lands the no-attribution
gate that protects the engineering-suite pivot, and brings the memory
index in sync. No application code is touched in M0.

## Conventions used in this file

This plan, like every artifact in the repo, never writes the blocked
upstream name literally. References use these placeholders:

- `<UPSTREAM>` — the blocked upstream agent-builder project's name.
  The literal string lives in exactly two places: the memory rule-doc
  (a single file under `~/.claude/projects/-home-admin1-Desktop-rapidly/memory/`,
  the only one whose slug matches `feedback_no_*_attribution`) and
  the `BLOCKED_PATTERN` GitHub Actions secret. Wiki-links written as
  `[[no-<UPSTREAM>-attribution-anywhere]]` are expanded by the
  executor when writing to a memory file (outside the repo).
- `$PATTERN` — shell variable holding the literal string at run time,
  loaded from the rule-doc memory file. Always `unset` after use.

The executor loads `$PATTERN` once at the top of a session:

```bash
RULE_DOC=$(ls ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/feedback_no_*_attribution.md | head -1)
test -f "$RULE_DOC" || { echo "rule-doc not found"; exit 1; }
PATTERN=$(awk '/^name:/{print $2}' "$RULE_DOC" | sed 's/^no-//; s/-attribution-anywhere$//')
test -n "$PATTERN" || { echo "could not derive pattern"; exit 1; }
# ... run M0 steps ...
unset PATTERN RULE_DOC
```

The `$PATTERN` value never appears in this file, in `git log`, in any
script committed to the repo, or in shell history (the executor uses
`HISTCONTROL=ignorespace` and prefixes commands with a space).

---

## 0. Pre-flight (read-only checks before any destructive action)

Already executed during planning, recorded here so re-running is safe:

| Check | Command | Expected | Status |
|---|---|---|---|
| Salvage scan | `gh pr view <N> --json reviews,comments` for each of the 22 PRs | only `github-actions` bot items | confirmed clean |
| Engineering-suite plan present | `test -f RAPIDLY_ENGINEERING_SUITE_PLAN.md` | exit 0 | confirmed |
| No leak in plan | `git grep -iEw "$PATTERN" -- RAPIDLY_ENGINEERING_SUITE_PLAN.md` | empty | confirmed |
| Memory rule-doc present | `test -f "$RULE_DOC"` | exit 0 | confirmed |
| Working tree | `git status --porcelain` | only the M0 plan + workflow file at end of M0 | TBD |

Stop and re-investigate if any row flips before executing the
destructive steps below.

---

## 1. Close the 22 abandoned PRs

### 1.1 The list

These are the PRs opened during the Plane-mirror push. Dependabot PRs
in the same number range (`#697`, `#707`, `#709`, `#710`) are **not**
ours and stay open.

```
698 699 700 701 702 703 704 705 706 708
711 712 713 714 715 716 717 718 719 720 721 722
```

### 1.2 Branch policy

- **Keep the branches.** Closing leaves `feat/projects-*` refs on the
  remote so anyone can `git checkout` later if a fragment becomes
  useful. Re-opening a closed PR also requires the branch to still
  exist.
- **Do not delete locally either.** Local branches are evidence of the
  abandoned work and cost nothing.

### 1.3 The closing comment

Same body for every PR. Written so a future reader who lands here
from a deep-link understands why the PR is dead without needing the
plan.

```
Closing without merging.

This PR was part of a 22-PR run that mirrored Plane's project-
management domain into Rapidly. The product direction changed before
any of these landed on main — see `RAPIDLY_ENGINEERING_SUITE_PLAN.md`
on the default branch for the new direction (engineering-suite
platform: agent builder + 3D/4D coordination + the existing markup
chamber).

The branch is left intact in case a fragment is worth lifting later,
but none of these PRs are merging as-is. M0 of the new plan
(`M0_EXECUTION.md`) closes the whole batch in one pass.
```

### 1.4 The command

Run from the repo root.

```bash
for n in 698 699 700 701 702 703 704 705 706 708 \
         711 712 713 714 715 716 717 718 719 720 721 722; do
  gh pr close "$n" --comment "$(cat <<'EOF'
Closing without merging.

This PR was part of a 22-PR run that mirrored Plane's project-
management domain into Rapidly. The product direction changed before
any of these landed on main — see `RAPIDLY_ENGINEERING_SUITE_PLAN.md`
on the default branch for the new direction (engineering-suite
platform: agent builder + 3D/4D coordination + the existing markup
chamber).

The branch is left intact in case a fragment is worth lifting later,
but none of these PRs are merging as-is. M0 of the new plan
(`M0_EXECUTION.md`) closes the whole batch in one pass.
EOF
)"
done
```

Flags:

- `--delete-branch` is **omitted on purpose**. See §1.2.
- The HEREDOC body uses `<<'EOF'` (quoted) so nothing in the comment
  is shell-expanded.

### 1.5 Verification

```bash
gh pr list --state open --limit 50 --json number \
  -q '.[] | .number' \
  | sort -n > /tmp/m0_after_close.txt

# None of these should appear:
for n in 698 699 700 701 702 703 704 705 706 708 \
         711 712 713 714 715 716 717 718 719 720 721 722; do
  grep -qx "$n" /tmp/m0_after_close.txt && echo "STILL OPEN: $n"
done
# Expected output: (nothing)
```

---

## 2. Land the no-attribution grep gate

### 2.1 Design choices

- **GitHub Action only, no pre-commit hook in M0.** The repo has no
  versioned hook framework (`.husky/`, `pre-commit`, etc. all absent)
  so adding one means also adding adoption tooling. Defer to a later
  milestone if developers want local feedback.
- **Pattern lives in a repo secret, not in the workflow file.** The
  workflow YAML must be checkable into the repo without itself
  matching the pattern. The job reads `${{ secrets.BLOCKED_PATTERN }}`
  at run time.
- **Scope: PR diffs only.** The check runs against the PR's diff
  against `main`, not a full-repo scan. This avoids tripping on the
  commit that introduces the workflow itself and keeps the job fast.
- **Case-insensitive, anchored to whole tokens.** Use `grep -iEw` to
  avoid matching substrings of unrelated identifiers. The blocked
  upstream is a coined name with no realistic English substrings to
  worry about; if a false positive ever surfaces, fix the pattern in
  the secret, not the workflow.

### 2.2 Repo secret

Set once, **via the GitHub web UI**:

1. Go to *Settings → Secrets and variables → Actions → New repository
   secret*.
2. Name: `BLOCKED_PATTERN`.
3. Value: open the rule-doc memory file (the only file under
   `~/.claude/projects/-home-admin1-Desktop-rapidly/memory/` whose
   slug matches `feedback_no_*_attribution`) and paste the exact
   string referenced in its body. Lowercase, no quotes.

We use the web UI on purpose so the literal value never appears in
shell history, `~/.bash_history`, the terminal scrollback, or any
process listing. After saving, the secret is only retrievable inside
Actions runs.

### 2.3 Workflow file

Path: `.github/workflows/no-attribution.yml`

```yaml
name: no-attribution

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: no-attribution-${{ github.ref }}
  cancel-in-progress: true

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Determine diff base
        id: base
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            echo "ref=origin/${{ github.base_ref }}" >> "$GITHUB_OUTPUT"
          else
            echo "ref=HEAD~1" >> "$GITHUB_OUTPUT"
          fi

      - name: Scan diff for blocked pattern
        env:
          PATTERN: ${{ secrets.BLOCKED_PATTERN }}
          BASE: ${{ steps.base.outputs.ref }}
        run: |
          set -euo pipefail

          if [ -z "${PATTERN:-}" ]; then
            echo "::error::BLOCKED_PATTERN secret is not set."
            exit 1
          fi

          # Diff = added lines + new file paths.
          # `git diff` with unified=0 + the `^+` filter strips context
          # and removals so we only block on what THIS change introduces.
          # The workflow file itself never contains the pattern (it's
          # in a secret), so it cannot self-trip.
          if git diff --unified=0 "$BASE"...HEAD \
               | grep -E '^\+' \
               | grep -v '^\+\+\+ ' \
               | grep -iEw "$PATTERN"; then
            echo "::error::Forbidden upstream reference detected in this change."
            echo "::error::See M0_EXECUTION.md and the no-attribution rule."
            exit 1
          fi

          # Also block on filenames containing the pattern.
          if git diff --name-only "$BASE"...HEAD \
               | grep -iEw "$PATTERN"; then
            echo "::error::Forbidden upstream reference in a filename."
            exit 1
          fi
```

Notes:

- `set -euo pipefail` plus the explicit empty-secret check make a
  mis-configured runner fail loud, not silently pass.
- `grep -E '^\+' | grep -v '^\+\+\+ '` strips diff headers so we only
  scan added content.
- Branch-protection enforcement is §2.5; do not require the check
  until the workflow has run at least once successfully.

### 2.4 Smoke test (do this before requiring the check)

On a throwaway branch:

```bash
git checkout -b chore/no-attr-smoke

# Bring $PATTERN into scope just for this command, then unset.
RULE_DOC=$(ls ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/feedback_no_*_attribution.md | head -1)
PATTERN=$(awk '/^name:/{print $2}' "$RULE_DOC" | sed 's/^no-//; s/-attribution-anywhere$//')

# Write a tripping file using printf so the literal does NOT enter
# shell history (assuming HISTCONTROL=ignorespace and a leading space):
 printf 'tripwire %s\n' "$PATTERN" > tripwire.txt
git add tripwire.txt
git commit -m "smoke: tripwire (expected to fail no-attribution gate)"
git push -u origin chore/no-attr-smoke
unset PATTERN RULE_DOC

# Open a PR via the URL printed above. Expected: scan job red.
# After confirming red, close the PR and delete the branch:
gh pr close chore/no-attr-smoke --delete-branch
```

The workflow itself is introduced via a **separate** PR that contains
only `.github/workflows/no-attribution.yml` and `M0_EXECUTION.md` —
no tripwire content — so the workflow's own first run is green.

### 2.5 Branch protection

Once the workflow has run green once on `main`:

```bash
# Fetch the current protection JSON so we add `scan` to the existing
# contexts list instead of clobbering it.
gh api "repos/rapidly-tech/rapidly/branches/main/protection" \
  > /tmp/protection.json

# Edit /tmp/protection.json in your editor and add "scan" to
# .required_status_checks.contexts (preserve every other field).

gh api -X PATCH "repos/rapidly-tech/rapidly/branches/main/protection" \
  --input /tmp/protection.json
```

---

## 3. Memory updates

These edits commit the pivot. They go in the user's auto-memory at
`~/.claude/projects/-home-admin1-Desktop-rapidly/memory/`, **not** in
the repo.

### 3.1 `MEMORY.md` diff

Edit `~/.claude/projects/-home-admin1-Desktop-rapidly/memory/MEMORY.md`.
Section: `## Product Direction (Apr 2026)`.

Add at the top of that section, above the existing entries:

```markdown
- [Engineering-suite pivot (May 2026)](project_engineering_suite_pivot.md) — Rapidly is being repositioned as an engineering-suite platform (agent builder + 3D/4D coordination + the existing markup chamber). Supersedes the Plane-mirror push and the 6-chamber revolver framing for new work.
```

Then edit the existing entries in the same section so future-me does
not re-act on them:

- `project_projects_domain.md` line — append ` **[ABANDONED 2026-05-21 — superseded by engineering-suite pivot; do not extend]**` to the description.
- `project_platform_direction.md` line — append ` **[SUPERSEDED 2026-05-21 — engineering-suite framing replaces the 6-chamber revolver for new work; existing chambers stay live]**` to the description.

Leave the per-chamber phase memories (`project_phase_b_complete.md`,
`project_phase_c_d_progress.md`, `project_phase_e_progress.md`) and
the whiteboard Excalidraw entry untouched — they describe shipped or
in-progress chambers that remain part of the platform.

### 3.2 New memory file: `project_engineering_suite_pivot.md`

Path:
`~/.claude/projects/-home-admin1-Desktop-rapidly/memory/project_engineering_suite_pivot.md`

```markdown
---
name: engineering-suite-pivot
description: As of 2026-05-21 Rapidly is being repositioned as an engineering-suite platform. The plan of record is RAPIDLY_ENGINEERING_SUITE_PLAN.md on main. M0 closed the 22 abandoned Plane-mirror PRs.
metadata:
  type: project
---

The product direction changed in May 2026. The new plan of record is
`RAPIDLY_ENGINEERING_SUITE_PLAN.md` at the repo root.

**What changed:** Rapidly stops being framed as a 6-chamber P2P
platform with a Plane-equivalent PM product bolted on. Instead it is
framed as a self-hosted engineering-suite: agent / workflow builder
(clean-room rewrite, see [[no-<UPSTREAM>-attribution-anywhere]]) plus
3D/4D coordination ("agentic iConstruct" — note: agentic, not a
clone of any vendor's product) plus the existing markup / whiteboard
chamber. Existing chambers (Files, Screen, Watch, Call, Collab) stay
live and supported.

**Why:** User wants Rapidly to read as a full engineering suite, not
a derivative of any single upstream. The Plane-mirror PR run (22 PRs
under `feat/projects-*`, opened May 2026) was closed in M0 of the new
plan — see `M0_EXECUTION.md` for the closing record. None of those
PRs merged; their branches remain on the remote in case a fragment
becomes useful, but the design they implement is not what we are
building.

**How to apply:**
- Plan of record is `RAPIDLY_ENGINEERING_SUITE_PLAN.md`. Read it
  before suggesting architectural direction.
- Do not extend the `feat/projects-*` work. If a feature feels like
  "more Plane parity", stop and check whether it belongs under the
  agent builder, the coordination layer, or the markup chamber
  instead.
- All work in the agent-builder domain is clean-room — see
  [[no-<UPSTREAM>-attribution-anywhere]] and
  [[feedback_clean_room_policy]].
- Model viewers and IFC tooling must be self-hosted, OSS-licensed
  (xeokit-sdk, IfcOpenShell, etc.). No SaaS viewer dependencies.
- AI features are scoped exclusively to the agent-builder chamber,
  per [[feedback_no_ai]]. Other chambers remain AI-free.
```

**Executor note:** before writing the file above to disk, expand
`<UPSTREAM>` in the two wiki-links to the actual slug used in the
rule-doc memory file's frontmatter `name:` field (which lives outside
the repo and is fine to reference there).

### 3.3 No edits to the rule-doc memory file

The rule-doc memory file is the single allowed home of the forbidden
upstream name. It is correct as written; do not re-touch it in M0.

---

## 4. Acceptance checklist

M0 is done when all of the following are true. Execute the checks in
order; each one is a one-liner. The checklist assumes `$PATTERN` has
been loaded into the shell as described in *Conventions*.

- [ ] **All 22 PRs closed.** `gh pr list --state open --search "head:feat/projects-"` returns zero rows.
- [ ] **Closing comment present on each.** `for n in 698 699 700 701 702 703 704 705 706 708 711 712 713 714 715 716 717 718 719 720 721 722; do gh pr view "$n" --json comments -q '.comments[].body' | grep -q "M0_EXECUTION.md" || echo "MISSING ON $n"; done` returns nothing.
- [ ] **Branches still exist on remote.** `git ls-remote --heads origin "feat/projects-*" | wc -l` ≥ 22.
- [ ] **Workflow file committed.** `test -f .github/workflows/no-attribution.yml` exit 0.
- [ ] **Workflow file is clean.** `grep -iEw "$PATTERN" .github/workflows/no-attribution.yml` returns nothing.
- [ ] **Secret is set.** `gh secret list --app actions | grep -q '^BLOCKED_PATTERN'` exit 0.
- [ ] **Workflow ran green once on main.** `gh run list --workflow=no-attribution.yml --branch=main --limit=1 --json conclusion -q '.[0].conclusion'` returns `success`.
- [ ] **Branch protection requires `scan`.** `gh api repos/rapidly-tech/rapidly/branches/main/protection --jq '.required_status_checks.contexts' | grep -q '"scan"'` exit 0.
- [ ] **Whole-repo scan is clean.** `git grep -iEw "$PATTERN" -- . ':!M0_EXECUTION.md' ':!RAPIDLY_ENGINEERING_SUITE_PLAN.md' | wc -l` returns `0`. The two allowlisted plan files use `<UPSTREAM>` / `$PATTERN` indirection and contain no literal occurrence — re-grep them too with `git grep -iEw "$PATTERN" -- M0_EXECUTION.md RAPIDLY_ENGINEERING_SUITE_PLAN.md`, which must also return zero.
- [ ] **MEMORY.md updated.** `grep -q 'engineering-suite-pivot' ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/MEMORY.md` exit 0.
- [ ] **Pivot memory file present.** `test -f ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/project_engineering_suite_pivot.md` exit 0.
- [ ] **Superseded memories annotated.** `grep -q 'ABANDONED 2026-05-21' ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/MEMORY.md && grep -q 'SUPERSEDED 2026-05-21' ~/.claude/projects/-home-admin1-Desktop-rapidly/memory/MEMORY.md` exit 0.
- [ ] **M0 commit landed.** A single commit on `main` titled `chore: M0 reset & no-attribution gate` containing only the new workflow file and `M0_EXECUTION.md`.
- [ ] **`unset PATTERN RULE_DOC`** ran before the executor exits the session.

When every box ticks, M1 (per `RAPIDLY_ENGINEERING_SUITE_PLAN.md`) is
ready to start.

---

## 5. Rollback

M0 is mostly reversible.

| Action | Reverse |
|---|---|
| 22 PRs closed | `gh pr reopen <N>` per PR. Branches were not deleted. |
| Workflow file added | `git revert <sha>` |
| `BLOCKED_PATTERN` secret set | Delete via *Settings → Secrets → Actions* in the web UI |
| Branch protection updated | `gh api -X PATCH repos/rapidly-tech/rapidly/branches/main/protection` with the prior context list |
| Memory edits | git is not in the loop; restore by hand from the diff above or re-write |

The one thing that does not rewind cleanly is the **closing comment**
on each PR — it remains in the comment timeline even after a re-open.
If you reopen and the comment is misleading, post a clarifying
follow-up rather than deleting.
