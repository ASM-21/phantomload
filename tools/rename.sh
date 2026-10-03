#!/usr/bin/env bash
# Rename the project end to end. See "About the name" in README.md for why.
#
#   tools/rename.sh dr-realization DrRealization
#
# Arg 1 is the distribution / directory name (hyphens allowed).
# Arg 2 is optional prose capitalisation for headings; defaults to arg 1.
#
# Renames the package directory, rewrites imports, packaging metadata, the
# citation file and every doc reference, then runs the tests and the claims
# guard so a failed rename cannot pass silently.
set -euo pipefail

NEW_DIST="${1:?usage: rename.sh <new-dist-name> [PROSE NAME]}"
NEW_PROSE="${2:-$NEW_DIST}"
NEW_PKG="${NEW_DIST//-/_}"
OLD_DIST="phantomload"
OLD_PKG="phantomload"
OLD_PROSE="PhantomLoad"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -d "$OLD_PKG" ]]; then
  echo "no $OLD_PKG package directory here; already renamed?" >&2
  exit 1
fi

echo "renaming $OLD_DIST -> $NEW_DIST (package $NEW_PKG, prose $NEW_PROSE)"

git mv "$OLD_PKG" "$NEW_PKG" 2>/dev/null || mv "$OLD_PKG" "$NEW_PKG"

# order matters: prose first, then package identifiers, so a prose occurrence
# inside a path is not half-rewritten
files=$(git ls-files 2>/dev/null || find . -type f -not -path './.git/*')
for f in $files; do
  case "$f" in *.png|*.csv|*.gz) continue ;; esac
  [[ -f "$f" ]] || continue
  sed -i "s/${OLD_PROSE}/${NEW_PROSE}/g; s/${OLD_PKG}/${NEW_PKG}/g; s/${OLD_DIST}/${NEW_DIST}/g" "$f"
done

echo "--- tests"
python -m pytest -q
echo "--- claims"
python tools/check_claims.py
echo
echo "renamed. Remaining by hand:"
echo "  - the repository name on the remote"
echo "  - the tagline in README, which still describes the old framing"
echo "  - the About the name section, which should become a note that it WAS renamed"
