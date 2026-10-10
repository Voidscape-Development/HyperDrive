#!/usr/bin/env bash
# Pushes HEAD to a branch from a GitHub Actions job, for workflows that commit
# to the branch they run on.
#
# Several workflows push to main (locale files, the frontend build, layout
# previews), and one pushing while another runs gets the other's push
# rejected. On a rejected push this puts HEAD's commits on top of the branch
# and tries again.
#
# Usage: scripts/push_with_retry.sh <branch>

set -u

branch="$1"
attempts=5

for attempt in $(seq 1 "$attempts"); do
  if git push origin "HEAD:$branch"; then
    exit 0
  fi
  if [ "$attempt" -eq "$attempts" ]; then
    break
  fi
  echo "Push rejected (attempt $attempt), rebasing onto origin/$branch"
  sleep $((attempt * 5))
  git fetch origin "$branch"
  if ! git rebase "origin/$branch"; then
    git rebase --abort
    echo "::error::The commit doesn't rebase cleanly onto origin/$branch"
    exit 1
  fi
done

echo "::error::Couldn't push to $branch after $attempts attempts"
exit 1
