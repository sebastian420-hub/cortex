#!/usr/bin/env bash
# Run one Cortex task on a schedule (cron, a systemd timer, anything that can run a command).
#
# What it adds around `cortex run`:
#   - a lock, so a slow run is never overlapped by the next one
#   - a wall-clock limit that also covers a model call that hangs
#   - the JSON result, the agent's commentary and a summary, kept per run
#   - optionally, pushing the branch of a run that VERIFIED (never one that did not)
#   - clean-up of old results
#
# Settings come from the environment (a systemd EnvironmentFile, or the top of a crontab):
#   CORTEX_REPO          the git repository to work on                        (required)
#   CORTEX_TASK_FILE     a file that contains the task                        (required)
#   CORTEX_VERIFY        the command that must pass, e.g. "python -m pytest -q"  (required)
#   CORTEX_RESULTS       where results go                  (default: ~/.cortex/runs)
#   CORTEX_WALL_TIMEOUT  seconds before the run is stopped (default: 5400)
#   CORTEX_PUSH          1 = push the branch of a run that verified to "origin" (default: 0)
#   CORTEX_KEEP_DAYS     delete results older than this    (default: 30)
#   CORTEX_BIN           the cortex command                (default: cortex)
# Anything after the script name is passed to `cortex run`, for example:
#   run-task.sh --provider openai --model qwen3-coder --protect 'tests/*' --require-sandbox
#
# Exit code: Cortex's own (0 completed as asked, 1 ran and did not succeed, 2 could not start),
# 124 if the wall-clock limit stopped it, 3 if a requested push failed. A run skipped because the
# previous one is still going exits 0 and says so.

set -u

: "${CORTEX_REPO:?set CORTEX_REPO to the git repository}"
: "${CORTEX_TASK_FILE:?set CORTEX_TASK_FILE to a file containing the task}"
: "${CORTEX_VERIFY:?set CORTEX_VERIFY to the command that must pass}"

bin=${CORTEX_BIN:-cortex}
results=${CORTEX_RESULTS:-$HOME/.cortex/runs}
wall=${CORTEX_WALL_TIMEOUT:-5400}
keep_days=${CORTEX_KEEP_DAYS:-30}

mkdir -p "$results" || exit 2

if command -v flock >/dev/null 2>&1; then
  exec 9>"$results/.lock"
  if ! flock -n 9; then
    echo "cortex: the previous run is still going; skipping this one" >&2
    exit 0
  fi
else
  echo "cortex: 'flock' not found, so overlapping runs are not prevented" >&2
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
result="$results/$stamp.json"
log="$results/$stamp.log"
summary="$results/$stamp.summary"

# On a time-out `timeout` sends TERM, which makes Cortex stop at its next step and clean up its
# worktree; it is killed outright only if that takes more than a minute longer.
timeout --signal=TERM --kill-after=60 "$wall" \
  "$bin" run \
    --project-dir "$CORTEX_REPO" \
    --task-file "$CORTEX_TASK_FILE" \
    --verify "$CORTEX_VERIFY" \
    --output "$result" \
    "$@" >"$summary" 2>"$log"
code=$?

# Read one field of the JSON result ("" if there is no result, e.g. the process was killed)
field() {
  python3 - "$result" "$1" <<'PY' 2>/dev/null
import json, sys
try:
    value = json.load(open(sys.argv[1])).get(sys.argv[2])
    print("" if value is None else value)
except Exception:
    print("")
PY
}
status=$(field status)
branch=$(field branch)

[ -s "$summary" ] && cat "$summary"
if [ -z "$status" ]; then
  echo "cortex: no result was written (exit $code); see $log"
else
  echo "cortex: $status (exit $code); result $result"
fi

# Only a run that VERIFIED is pushed: "unverified", failed and interrupted runs are not
if [ "$code" -eq 0 ] && [ "$status" = "passed" ] && [ -n "$branch" ] \
   && [ "${CORTEX_PUSH:-0}" = "1" ]; then
  if git -C "$CORTEX_REPO" push origin "$branch"; then
    echo "cortex: pushed $branch to origin"
  else
    echo "cortex: pushing $branch failed" >&2
    code=3
  fi
fi

find "$results" -maxdepth 1 -type f \( -name '*.json' -o -name '*.log' -o -name '*.summary' \) \
  -mtime +"$keep_days" -delete 2>/dev/null

exit "$code"
