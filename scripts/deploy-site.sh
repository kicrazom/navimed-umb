#!/usr/bin/env bash
# Publikuje site/ na gałąź gh-pages (GitHub Pages serwuje ją z roota).
#
# Pages jest skonfigurowane jako legacy build z gałęzi `gh-pages`, path `/`.
# Nie ma workflow — bez tego skryptu deploy jest ręczny i zapomina się o nim.
# Historia: między 2026-07-11 a 2026-08-23 strona stała nieaktualna przez sześć tygodni.
#
# Użycie:  scripts/deploy-site.sh [--dry-run]
set -euo pipefail

REPO=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
cd "$REPO"
SRC=site
BRANCH=gh-pages
WT=$(mktemp -d)
DRY=${1:-}

command -v rsync >/dev/null || { echo "BŁĄD: brak rsync"; exit 1; }
[ -d "$SRC" ] || { echo "BŁĄD: brak katalogu $SRC"; exit 1; }

cleanup() { git worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$WT"; }
trap cleanup EXIT

echo "[1/4] pobieram $BRANCH"
git fetch -q origin "$BRANCH"
git worktree add -q --detach "$WT" "origin/$BRANCH"
git -C "$WT" checkout -q -B "$BRANCH" "origin/$BRANCH"

echo "[2/4] synchronizuję $SRC/ -> $BRANCH"
# ponytail: --delete, żeby usunięte strony znikały też z produkcji;
# _* to lokalne narzędzia podglądu (skrypty, logi, snapshoty) — nie publikujemy ich
rsync -a --delete \
  --exclude '_*' \
  --exclude '.git' \
  "$SRC"/ "$WT"/
touch "$WT/.nojekyll"          # bez tego Pages przepuszcza wszystko przez Jekylla

echo "[3/4] zmiany"
git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
  echo "  brak zmian — nic do publikacji"; exit 0
fi
git -C "$WT" --no-pager diff --cached --stat | tail -20

if [ "$DRY" = "--dry-run" ]; then
  echo "[4/4] --dry-run: nie commituję i nie wypycham"; exit 0
fi

echo "[4/4] commit + push"
git -C "$WT" commit -q -m "deploy: site @ $(git rev-parse --short HEAD)"
git -C "$WT" push -q origin "$BRANCH"
echo "OK -> https://kicrazom.github.io/navimed-umb/  (Pages przebuduje się w ~1 min)"
