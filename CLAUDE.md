# Claude Code — Standing Rules for This Project

These rules are permanent and apply to every session working in this
repository. They are not suggestions or defaults to override when
convenient — they hold even when a specific request in the moment seems
to call for an exception.

## 1. Never perform any Git write operation

No `git commit`, `git push`, `git tag`, `git merge`, `git rebase`,
`git branch`, or any other operation — local or GitHub-hosted (`gh`) —
that writes to the repository or to GitHub. **No exceptions**, including
when explicitly asked to do so in the moment. The human handles all Git
operations manually, always.

Reading, analyzing, and preparing files for a future commit is expected
and fine — the line is at anything that actually writes to the repo or
to GitHub. Read-only commands (`git status`, `git diff`, `git log`,
read-only `gh` lookups) are fine.

If asked to commit, push, or similar: leave the files ready and say so —
do not run the command.

## 2. Allman brace style for all new code

Every opening brace (`{`) starts on its own line, for every block —
functions, conditionals, loops, classes, everything. Applies to all new
code in this project, in every package.

Known exception: most of `APP/mobile/src` predates this convention being
made explicit and still uses K&R-style braces (`{` on the same line).
This is tracked in `docs/BACKLOG.md` as its own cleanup item — don't
silently reformat unrelated existing code to Allman as a side effect of
an unrelated change; that's a separate, deliberate pass.

## 3. Never make product or architecture decisions unilaterally

Whenever a task hits a genuine decision point, ambiguity, or
uncertainty — a product choice, an architectural fork, anything with
more than one reasonable resolution — stop and ask before proceeding.
Don't pick a default and move on.

Purely mechanical implementation details with no real alternative (the
only way to actually make an already-approved requirement work) don't
need to block on a question, but should still be flagged clearly
afterward so the choice is visible, not silent.

## 4. Read the Expo version instructions before touching mobile

Before making any change to `APP/mobile/`, read `AGENTS.md` at the
project root — it currently flags that the Expo SDK has changed enough
that Expo's own versioned docs need checking before writing mobile code.

---

For the system's architecture, conventions, and design decisions, see
[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md). For open/planned work,
see [`docs/BACKLOG.md`](./docs/BACKLOG.md).
