#!/usr/bin/env bash
# Open an issue for a weekly check that found a problem, or comment on the open one.
set -euo pipefail

title="${CHECK_NAME} found a problem"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
body_file=$(mktemp)
trap 'rm -f "$body_file"' EXIT

{
  echo "${CHECK_NAME} on $(date -u +%Y-%m-%d) found a problem: ${run_url}"
  found=0
  if [ -d "${FINDINGS_DIR:-}" ]; then
    while IFS= read -r findings; do
      printf '\n%s\n' "$(cat "$findings")"
      found=1
    done < <(find "$FINDINGS_DIR" -name findings.md | sort)
  fi
  if [ "$found" -eq 0 ]; then
    printf '\nNo findings were recorded, so the check may not have finished. See the run.\n'
  fi
} > "$body_file"

# GitHub rejects an issue body over 65536 characters, which would mean no issue at all.
if [ "$(wc -c < "$body_file")" -gt 64000 ]; then
  head -c 63000 "$body_file" > "$body_file.cut" && mv "$body_file.cut" "$body_file"
  printf '\n\n(Truncated. See the run.)\n' >> "$body_file"
fi

# Reuse only an open issue this workflow opened. The title reaches jq as
# data, not code, and anyone can open an issue with the same title.
existing=$(TITLE="$title" gh issue list --repo "$GITHUB_REPOSITORY" --state open \
  --limit 200 --json number,title,author \
  --jq 'map(select(.title == env.TITLE and .author.login == "app/github-actions"))
        | .[0].number // empty')

if [ -n "$existing" ]; then
  gh issue comment "$existing" --repo "$GITHUB_REPOSITORY" --body-file "$body_file"
  exit 0
fi

printf '\nClose this issue once the cause is fixed. Until then, later findings are added here as comments.\n' >> "$body_file"
url=$(gh issue create --repo "$GITHUB_REPOSITORY" --title "$title" --body-file "$body_file")
echo "$url"
# Assigning notifies the assignees. Done after creation, so an assignee who
# lost access leaves the issue open and unassigned rather than missing.
if [ -n "${ISSUE_ASSIGNEES:-}" ]; then
  gh issue edit "$url" --repo "$GITHUB_REPOSITORY" --add-assignee "$ISSUE_ASSIGNEES" \
    || echo "::warning::Could not assign ${ISSUE_ASSIGNEES} to ${url}"
fi
