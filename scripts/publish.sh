#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
[[ $(git remote get-url origin) == https://github.com/kalqor-os/kalqor-update.git ]] || {
  echo 'Unexpected origin. Check the repository before publishing.'; exit 1;
}
[[ $(git branch --show-current) == main ]] || { echo 'Switch to main before publishing.'; exit 1; }
python3 scripts/build-repo.py "$@"
git add -- docs scripts README.md .gitignore
if ! git diff --cached --quiet; then
  git commit -m 'Publish signed KALQOR APT repository'
fi
git push -u origin main
echo 'Push complete. Confirm GitHub Pages deployment before testing clients.'
