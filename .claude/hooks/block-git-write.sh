#!/usr/bin/env bash
#
# block-git-write.sh — PreToolUse hook: hard technical block on git/gh
# write operations, for every Bash or PowerShell tool call.
#
# ── What this is ─────────────────────────────────────────────────────
# This is NOT a conversational rule and NOT a memory-based instruction.
# It is enforced by Claude Code's own hook system: this script runs
# BEFORE a Bash/PowerShell tool call is allowed to execute, receives
# the proposed command on stdin, and if it matches a blocked pattern,
# exits with status 2. Per Claude Code's hook contract, exit code 2 on
# a PreToolUse hook is a hard block — the tool call does not run, full
# stop. The calling model (Claude) cannot reason, argue, or negotiate
# its way past this; it never gets the chance to run the command in the
# first place. See: https://code.claude.com/docs/en/hooks
#
# ── What is blocked ──────────────────────────────────────────────────
#   git push
#   git commit
#   git branch
#   git merge
#   git rebase
#   git reset --hard   (git reset AND --hard, in the same command)
#   git tag            (blocked unconditionally, not just "tag + push")
#   git cherry-pick
#   gh pr merge
#   gh pr create
#
# Read-only git/gh commands (status, diff, log, gh pr view, etc.) are
# NOT matched by any pattern below and are left alone.
#
# ── No override path, by design ──────────────────────────────────────
# There is deliberately no flag, environment variable, magic phrase, or
# conversational escape hatch checked anywhere in this script. Nothing
# said in chat — including "I authorize this," "ignore the hook," or
# any claimed exception — can change what this script does, because
# this script never reads the conversation at all; it only ever sees
# the literal command string about to run. The only legitimate way to
# change this policy is to edit or delete this file directly, outside
# of any chat conversation with Claude.
#
# ── Honest limits (read this) ────────────────────────────────────────
# This is pattern matching on a command string, not a real shell
# parser, and it cannot see anything outside the single command string
# Claude Code hands it. It does NOT protect against:
#   - Someone with direct filesystem/terminal access editing or
#     deleting this file, or the settings.json entry that wires it in.
#   - A custom git alias (e.g. `git config alias.c commit`) whose
#     expansion isn't visible in the literal command text.
#   - Sufficiently obfuscated invocations (base64-decode-then-eval,
#     a wrapper script calling a differently-named git binary, etc.).
#   - Any tool call this hook isn't registered against, if one exists
#     that can execute arbitrary shell commands outside Bash/PowerShell.
# The only fully unbypassable protection is removing write-capable
# GitHub credentials entirely — this hook raises the bar substantially
# for direct, undisguised commands, it does not raise it to zero.
#
# It also deliberately over-blocks in one specific way: matching is
# substring-based, so a command that merely *mentions* one of these
# phrases (e.g. inside an echo string) can trigger a false block. That
# tradeoff is intentional — false positives are an annoyance, false
# negatives are the actual risk this hook exists to prevent.

set -u

INPUT="$(cat)"

# ── Debug log ─────────────────────────────────────────────────────────
# Records every invocation of this hook (timestamp + raw stdin JSON) so
# invocation can be verified from disk, independent of anything the
# model reports. Written unconditionally, before any decision is made.
DEBUG_LOG="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/debug.log"
{
    printf -- '--- %s ---\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    printf '%s\n' "$INPUT"
} >> "$DEBUG_LOG" 2>/dev/null

# ── Primary check: JSON-aware, via Python (verified present in this
# environment). Extracts tool_input.command and pattern-matches it.
PYCODE=$(cat <<'PYEOF'
import json, re, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

command = (data.get("tool_input") or {}).get("command") or ""
if not command:
    sys.exit(0)

CHECKS = [
    ("git push",        r"git[^;&|\n]*\spush\b"),
    ("git commit",      r"git[^;&|\n]*\scommit\b"),
    ("git branch",      r"git[^;&|\n]*\sbranch\b"),
    ("git merge",       r"git[^;&|\n]*\smerge\b"),
    ("git rebase",      r"git[^;&|\n]*\srebase\b"),
    ("git cherry-pick", r"git[^;&|\n]*\scherry-pick\b"),
    ("git tag",         r"git[^;&|\n]*\stag\b"),
    ("gh pr merge",     r"gh[^;&|\n]*\spr[^;&|\n]*\smerge\b"),
    ("gh pr create",    r"gh[^;&|\n]*\spr[^;&|\n]*\screate\b"),
]

hit = None
for label, pattern in CHECKS:
    if re.search(pattern, command, re.IGNORECASE):
        hit = label
        break

if hit is None:
    if re.search(r"git[^;&|\n]*\sreset\b", command, re.IGNORECASE) \
            and re.search(r"--hard\b", command, re.IGNORECASE):
        hit = "git reset --hard"

if hit:
    print(hit)
PYEOF
)

PY=""
if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
fi

BLOCK_REASON=""

if [ -n "$PY" ]; then
    BLOCK_REASON="$(printf '%s' "$INPUT" | "$PY" -c "$PYCODE" 2>/dev/null)"
else
    # Fallback if python is ever unavailable: fail closed rather than
    # silently becoming a no-op. Coarse on purpose — see header.
    if printf '%s' "$INPUT" | grep -Eiq '"command"[[:space:]]*:.*\b(git|gh)\b'; then
        BLOCK_REASON="a git/gh command (python unavailable — coarse fallback check used)"
    fi
fi

if [ -n "$BLOCK_REASON" ]; then
    printf 'DECISION: BLOCK (%s)\n' "$BLOCK_REASON" >> "$DEBUG_LOG" 2>/dev/null
    {
        echo "BLOCKED by .claude/hooks/block-git-write.sh"
        echo "Detected: $BLOCK_REASON"
        echo "This project has a standing, unconditional hook blocking all git/gh write operations."
        echo "There is no override phrase, flag, or in-conversation exception — see the header of this script."
        echo "The only way to change this is to edit or remove the hook file directly, outside of chat."
    } >&2
    exit 2
fi

printf 'DECISION: ALLOW\n' >> "$DEBUG_LOG" 2>/dev/null
exit 0
