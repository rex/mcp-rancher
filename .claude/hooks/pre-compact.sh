#!/usr/bin/env bash
# PreCompact hook — fires before Claude Code compacts the conversation.
#
# Writes a forensic snapshot of TASK_STATE.md + PROGRESS.md to disk so we
# have a record of what state was active right before each compaction.
#
# Does NOT emit additionalContext: the PreCompact event has no injection
# mechanism for that. Its only honored top-level fields are `continue`,
# `stopReason`, and `suppressOutput`. The compacted summary is produced by
# Claude itself; SessionStart re-injects TASK_STATE / PROGRESS on the
# post-compact resume path, so no in-band injection is needed here.
#
# Fires on: PreCompact
# Emits:    nothing on stdout (silent success — exits 0)
# Side effect: rewrites .claude/last-pre-compact-snapshot.md

set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

mkdir -p .claude
snapshot=".claude/last-pre-compact-snapshot.md"

{
  echo "# Pre-compact snapshot"
  echo
  echo "Captured: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo

  if [ -f TASK_STATE.md ]; then
    echo "## TASK_STATE.md (full)"
    echo
    cat TASK_STATE.md
    echo
  fi

  if [ -f PROGRESS.md ]; then
    echo "## PROGRESS.md"
    echo
    cat PROGRESS.md
    echo
  fi

  echo "## Note"
  echo
  echo "AGENTS.md and CLAUDE.md are re-loaded by the SessionStart hook after compaction."
} > "$snapshot"
