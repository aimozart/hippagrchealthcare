#!/usr/bin/env bash
# Usage: install.sh /path/to/repo  (copies the pre-commit and post-commit hooks; adds .gitignore entries if missing)
set -euo pipefail
repo="$1"; here="$(cd "$(dirname "$0")" && pwd)"
install -m 0755 "$here/pre-commit" "$repo/.git/hooks/pre-commit"
install -m 0755 "$here/post-commit" "$repo/.git/hooks/post-commit"
touch "$repo/.gitignore"
while IFS= read -r line; do grep -qxF -- "$line" "$repo/.gitignore" || echo "$line" >> "$repo/.gitignore"; done < "$here/../../.gitignore"
echo "installed hook and gitignore entries in $repo"
