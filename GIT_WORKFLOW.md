# Git workflow for circuit-analysis work

This guide is for hardware engineers using the HardwareDev workspace to investigate possible circuit design changes. It walks through the three things you'll do every week:

1. Create a branch to explore a change.
2. Open a pull request to merge that branch back into `main`.
3. Pull `main` into your branch so it stays current.

Plus a short section on resolving merge conflicts, commit-message and review conventions, and per-repo notes.

The instructions assume **VS Code's Source Control panel** for local work and the **GitHub website** for pull requests, because that's what the team standardized on. CLI fallbacks are shown only where the GUI is awkward.

---

## Mental model

The workspace contains three sibling git repos:

```
HardwareDev/
  hw_analysis_framework/   # the framework package
  components/              # the component library (types / families / instances)
  example_analysis/        # the worked-example analysis project
```

Each one has **its own** `.git/` folder, its own `main` branch, and its own pull-request history on GitHub. There is no super-repo. If a single change touches two repos — e.g., you add a new component *type* in `components/` and use it in a block in `example_analysis/` — you open **one PR per repo** and call out the dependency between them in each PR description.

**One branch per investigation.** A branch is cheap; create one per "what-if" you want to explore. Don't pile unrelated experiments onto the same branch — it makes the eventual PR hard to review and hard to revert if the analysis turns out wrong.

---

## One-time setup

You should only need to do this once per machine per repo.

1. **Sign in to GitHub from VS Code.** Open the Source Control panel (`Ctrl+Shift+G`), or the Accounts gear at the bottom-left of the window. Sign in with the GitHub account that has push access to the team's repos.
2. **Confirm the remote is set.** Open a PowerShell terminal in the repo folder and run `git remote -v`. You should see an `origin` pointing at the team's GitHub. If you see nothing, ask whoever set up the repo for the remote URL and run `git remote add origin <url>` once.
3. **Install the GitHub Pull Requests and Issues extension.** Marketplace ID `GitHub.vscode-pull-request-github`. It puts a "GitHub Pull Request" view in the sidebar and lets you create / review PRs without leaving the editor. (The web UI is still fine; the extension is a convenience.)
4. **Set your name and email** if you haven't:
   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@your.work.email"
   ```

---

## Creating a branch for a new investigation

Use this flow when you're about to explore *anything* that could land on `main` later — a derating change, a new block, a different op-amp, a tolerance tightening.

1. **Make sure you're on `main` and up to date.**
   - VS Code: bottom-left status bar shows the current branch. Click it. If it isn't `main`, pick `main` from the list. Then click the sync icon (the circular arrow next to the branch name) to pull the latest commits.
2. **Create the branch.**
   - VS Code: open the Command Palette (`Ctrl+Shift+P`) and run **`Git: Create Branch From...`**. Pick `main` as the base. Name the branch following the convention below.
3. **Switch to it** — VS Code does this automatically after creation.

**Branch naming.** Use `<your-initials>/<short-slug>`. Optional `investigate-` / `feat-` / `fix-` prefix on the slug if it helps:

```
mb/investigate-can-transceiver-derate
mb/feat-new-mosfet-family
mb/fix-tempco-unit-mismatch
```

Short, lowercase, hyphens, no spaces. The initials make `git branch -a` readable in a team.

### Push the branch up to GitHub the first time

After your first commit on the new branch:

- VS Code: click the cloud icon ("Publish Branch") in the status bar, or use the Command Palette → **`Git: Publish Branch`**. This is the GUI equivalent of `git push -u origin <branch>` — it tells GitHub the branch exists and links your local branch to it so future syncs work with one click.

After the first push, the status-bar icon turns into the standard sync arrow. Click it to push and pull future commits.

---

## Day-to-day: stage, commit, push

You'll typically do a cycle like this several times in an investigation:

1. **Edit** files. Save (`Ctrl+S`).
2. **Open Source Control** (`Ctrl+Shift+G`). Your changed files appear under "Changes."
3. **Stage** what you want to include in this commit. Hover a file and click the `+`. Stage hunks (not whole files) by opening the file's diff and clicking the `+` on the hunk you want — useful when you've made two unrelated edits in the same file and want them in separate commits.
4. **Write a commit message** in the box at the top. See the [commit message conventions](#commit-message-conventions) below. Press `Ctrl+Enter` to commit.
5. **Push** by clicking the sync icon in the status bar (after the first push — see above).

Commit often. Small commits are easier to review and easier to revert if one piece of an investigation turns out wrong.

---

## Opening a pull request

Open the PR as soon as you have something worth showing — even early. Mark it a **Draft** PR if it isn't ready for review yet. Drafts are the right way to get early feedback on an analysis approach before you've spent a week down a wrong path.

### From GitHub (recommended for the first PR you ever open)

1. Push your branch (see above).
2. Go to `github.com/<org>/<repo>` in a browser. GitHub usually shows a yellow banner across the top: *"Your branch <name> had recent pushes — Compare & pull request."* Click it.
3. **Base** is `main`. **Compare** is your branch. Confirm both.
4. **Title.** One line, present-tense, says what changed. "Derate CAN transceiver thermal margin to 110 °C T_J." Not "WIP" and not the branch name.
5. **Description.** Use this template:
   ```markdown
   ## What this changes
   <1–3 sentences. The actual change in the analysis or design.>

   ## Why
   <Link to the requirement, ticket, or incident driving this. Or "exploring whether
   the existing design holds up at hot ambient" — investigations are valid PRs.>

   ## What I checked
   - [ ] `pytest` passes locally (note any known-failing tests — see per-repo notes)
   - [ ] Notebook re-executes end-to-end (for example_analysis PRs)
   - [ ] Touched no Contracts owned by another block (see block ownership rule)

   ## What a reviewer should look at first
   <Point them at the load-bearing file or function. Reviewers' attention is finite.>
   ```
6. If the work isn't done, open the **Create pull request** dropdown and choose **Create draft pull request**.
7. **Assign a reviewer.** For circuit-analysis PRs the reviewer is normally the engineer who owns the affected schematic page (see block ownership rule, below). When in doubt, post in the team channel and ask who should look.

### From VS Code (after the extension is installed)

1. Open the **GitHub Pull Requests** view in the sidebar.
2. Click the `+` next to "Pull Requests" → **Create Pull Request**.
3. Fill in base (`main`), title, description. Same content as above.
4. Submit. The PR opens in the sidebar; you can review comments and merge from there without leaving the editor.

### Iterating on the PR

When reviewers leave comments:

1. Push more commits to the same branch. They appear in the PR automatically — you don't need to re-open anything.
2. Reply to comments inline. Resolve them only after you've addressed them.
3. When the PR is ready for real review, click **Ready for review** (turns a draft PR into a regular one).
4. Once approved, click **Squash and merge** (default) or **Merge** depending on what the repo's settings allow. Delete the branch afterward — the button GitHub offers right after merge is fine.

---

## Pulling `main` into your branch (keeping your branch fresh)

Long-running branches drift. If `main` moves while you're working on `mb/investigate-can-transceiver-derate`, you want to pull those new commits into your branch so the eventual PR merges cleanly and so you're analyzing against the *current* design, not a snapshot from two weeks ago.

There are two ways to do this. **Merge** is the safe default. **Rebase** gives a cleaner history but rewrites your commits, which is dangerous if anyone else has pulled your branch.

### Merge (default — do this one)

With your investigation branch checked out:

1. **Update your local copy of `main`.** VS Code Command Palette → **`Git: Fetch`**. (Fetch downloads new commits but doesn't change your working files.)
2. **Merge `main` into your branch.** Command Palette → **`Git: Merge Branch...`** → pick `main`.
3. If git reports no conflicts, you're done — push the merge commit (sync icon).
4. If git reports conflicts, see [the next section](#resolving-merge-conflicts).

### Rebase (only when nobody else has checked out your branch)

Same idea, but instead of merging, your commits get replayed on top of the latest `main`:

- Command Palette → **`Git: Rebase Branch...`** → pick `main`.
- Resolve any conflicts the same way as a merge (the workflow is identical from the conflict-resolution view).
- After a rebase, you'll need to **force-push**: `git push --force-with-lease`. (`--force-with-lease` is the safer cousin of `--force` — it refuses if someone else has pushed to your branch in the meantime.)

If unsure: merge.

---

## Resolving merge conflicts

A conflict happens when both `main` and your branch changed the *same lines* of the *same file* differently. Git can't pick for you.

VS Code makes this much less painful than the CLI:

1. After a merge or rebase that produced conflicts, the Source Control panel shows the conflicting files under "Merge Changes" with a `!` icon.
2. Click a conflicting file. VS Code shows the conflict inline with three buttons above each conflict block:
   - **Accept Current Change** — keeps your branch's version.
   - **Accept Incoming Change** — keeps `main`'s version.
   - **Accept Both Changes** — keeps both, in order. Useful when both edits are valid (e.g., you both added an entry to the same list).
3. There's also a **"Open Merge Editor"** button at the bottom of the file. It opens a three-pane view (your version, their version, the merged result you're building) which is the right tool when neither side is wholly correct and you need to hand-craft the merge.
4. After resolving every conflict in the file, **save** it. The `!` clears and the file moves to "Staged Changes."
5. When all files are clean, commit. VS Code pre-fills a merge commit message — accept it.

### Conflict-resolution rules of thumb for this codebase

- **`leaves.py` / `analysis.py` parameter names** — if a function's parameter names changed on `main` because someone renamed a Hamilton node, you usually want their version. Hamilton wires by name, so keeping your old name will break the DAG silently.
- **`scenarios.toml` / `modes.toml` / `requirements.py`** — these are shared. If both branches added scenarios / modes / requirements, "Accept Both" is usually right. If both branches edited the same scenario's value, talk to the other engineer before picking — that's a design disagreement, not a merge conflict.
- **`Contract` definitions** — if you and `main` both edited the same Contract, stop and check the block ownership rule. Only one engineer should be publishing changes to any given Contract. If you're editing a Contract on a page you don't own, the merge resolution is "discard your edit and talk to the owner."
- **`pyproject.toml` / `poetry.lock`** — if both branches changed dependencies, accept both for `pyproject.toml`, then **delete `poetry.lock` and re-run `poetry lock`** in the affected repo. Don't hand-merge `poetry.lock`.

When in doubt, *abort* the merge (`git merge --abort`) and ask. An aborted merge leaves no trace.

---

## Commit message conventions

One line, ≤72 chars, present-tense imperative. Optionally a blank line and a longer body.

Good:

```
Derate CAN transceiver T_J ceiling to 110°C

Surfaces the hot_high_vin overshoot at active/diagnostic modes.
Updates blocks/can_transceiver/analysis.py and the matching
verification's bound. Driven by REQ-THERM-014.
```

Bad:

```
fix
WIP
updates
.
```

The body is where you put the *why*. If the change is driven by a requirement or ticket, name it (`REQ-THERM-014`, `JAMA-1834`, `INCIDENT-2026-04-09`). Future-you will thank present-you when grepping commit history.

For investigations that didn't land: commit honestly. `"Try derating to 105°C — fails REQ-PERF-001b"` is a fine commit message. It documents what you tried so the next person doesn't redo the experiment.

---

## Review etiquette

What makes a circuit-analysis PR reviewable:

- **Show the numerical change, not just the code change.** If you're tightening a tolerance, the PR description should say "RDS(on) max moves from 38 mΩ to 42 mΩ; the resulting T_J at `hot_high_vin/active` moves from 108 °C to 113 °C, which crosses the REQ-THERM-014 ceiling." Code diffs alone don't tell the reviewer whether the *physics* changed in a meaningful way.
- **Run the verifications before requesting review.** Paste the relevant rows of the verification table into the PR body. If a test is *supposed* to fail (see per-repo notes for `example_analysis`), say so.
- **One investigation per PR.** If you tried three derating strategies, that's three PRs (or three commits with very clear separation), not one PR with all three folded together.
- **Tag the schematic-page owner.** This is the block ownership rule (workspace `CLAUDE.md`, §6.7 of the design doc). Whoever owns the page your change touches is the right reviewer. If you're editing analysis on someone else's page, that's the wrong PR — you should be asking the owner to change it on your behalf.

As a reviewer, three things to always check:

1. **Units.** Does any arithmetic mix `degC` with `K`? Does any Pint string use prefixed-Ohm syntax? (See the framework `CLAUDE.md` gotchas list.)
2. **Block ownership.** Does this PR publish a Contract about a net or component on a page the author doesn't own? If yes, push back.
3. **Tests.** Did the author add or update tests / verifications for the changed analysis? A circuit-change PR with no test changes is suspicious — either the change is uncovered, or the existing tests weren't checking what we thought.

---

## Per-repo notes

The three repos look the same from git's perspective. They differ in what makes a PR reviewable and what "tests pass" means.

### `hw_analysis_framework/`

This is the framework package itself.

- **Test command:** `poetry run pytest` from inside the repo (uses `.venv/Scripts/python.exe`).
- **Bar for merge:** all tests passing, coverage holding (90%+ on framework, 100% on `Quantity` arithmetic per design doc §16), and mypy strict on `src/framework`. CI should enforce this.
- **What reviewers focus on:** alignment with the design doc section called out in the PR description. If the change disagrees with the design doc, the PR should either update the design doc in the same PR or explicitly flag the disagreement so it gets discussed.
- **Branch naming nuance:** if the change implements an item from §14 of the design doc, include the step number in the branch name (`mb/feat-step-11-standard-analyses`). Makes the PR easy to cross-reference with `PROJECT_STATUS.md`.

### `components/`

The component library — types, families, instances.

- **Test command:** from this repo, `..\hw_analysis_framework\.venv\Scripts\python.exe -m pytest`. No separate venv.
- **Bar for merge:** all tests passing. New `instances/` PRs need a one-line smoke test in `tests/test_instances.py`. New `types/` PRs need the "three real instances would adopt it" justification in the PR description, per `components/CLAUDE.md` and `CONTRIBUTING.md`.
- **What reviewers focus on:** the type / family / instance pattern (`components/CLAUDE.md`). Is the new thing in the right layer? Does a new component type belong as a type, or could it be `metadata` on an existing type?
- **Branch naming nuance:** `mb/instance-irlml6344` for a new instance, `mb/family-resistor-low-tempco` for a new family, `mb/type-current-sense-amp` for a new type. Makes the layer obvious from the branch name.

### `example_analysis/`

The worked-example analysis project. This is also where the block ownership rule actually bites.

- **Test command:** from this repo, `../hw_analysis_framework/.venv/Scripts/python.exe -m pytest tests/` plus re-executing the notebook (see the repo's `CLAUDE.md`).
- **Heads up: the thermal verification is *designed to fail*.** It surfaces the worked example's T_J overshoot at `hot_high_vin / {active, diagnostic}` — a "1 failed, 1 passed" exit code is the current steady state and is *correct*. A PR is fine to merge with the thermal verification still failing as long as the failure didn't change. If your PR makes a *different* verification fail, that needs explanation.
- **Bar for merge:** verifications produce the expected results (i.e., the only failures are the known-designed-to-fail ones), the notebook re-executes end-to-end, and the **block ownership rule** is respected (see below).
- **The block ownership rule.** Each schematic page has exactly one owner. That owner's block is the only place Contracts get published about nets and components on that page. If your PR adds or edits a Contract on a page you don't own, the merge resolution is: drop the change, ask the page owner to publish it instead. This is not yet mechanically enforced (it lands with step 6, the netlist parser) — until then it is a code-review concern. Workspace `CLAUDE.md` and `example_analysis/CLAUDE.md` both call this out; design doc §6.7 is authoritative.
- **Branch naming nuance:** `mb/block-can-transceiver-derate` for changes to an existing block, `mb/new-block-buck-12v-to-5v` for a new block.

---

## Cheat sheet

| What | VS Code | CLI fallback |
|---|---|---|
| Switch to `main` and update | Click branch in status bar → pick `main` → sync icon | `git checkout main && git pull` |
| Create a branch from `main` | `Ctrl+Shift+P` → `Git: Create Branch From...` → `main` | `git checkout -b mb/your-slug main` |
| Stage a hunk | Open file diff, `+` on the hunk | `git add -p` |
| Commit | Source Control panel, message in box, `Ctrl+Enter` | `git commit -m "..."` |
| First push of a new branch | Status bar cloud icon ("Publish Branch") | `git push -u origin <branch>` |
| Subsequent pushes | Status bar sync icon | `git push` |
| Pull `main` into your branch | Command Palette → `Git: Fetch` → `Git: Merge Branch...` → `main` | `git fetch && git merge main` |
| Abort a bad merge | Source Control panel "..." → `Abort Merge` | `git merge --abort` |
| See what changed in a file | Click the file in Source Control panel | `git diff <file>` |
| See branch history | Install the **Git Graph** extension; click the branch icon in the bottom status bar | `git log --oneline --graph --all` |

---

## When you're stuck

- A merge looks scary: **abort it** (`git merge --abort` or the VS Code menu option). Nothing is lost.
- You committed to the wrong branch: don't panic. The commit is recoverable. Ask before doing anything that touches history (`reset`, `rebase`, `cherry-pick`) — these can lose work if done wrong.
- VS Code can't find tests after switching branches: check the Python interpreter is still `hw_analysis_framework/.venv/Scripts/python.exe` (Ctrl+Shift+P → "Python: Select Interpreter"). Branch switches sometimes nudge this.
- You're not sure whether your edit belongs in your branch or someone else's: ask in the team channel before you commit, not after. The block ownership rule is the most common case of this.
