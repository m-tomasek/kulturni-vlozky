#!/usr/bin/env bash
# Uložení po sběru na GitHubu: soubory pro web, commit dat do repa a hlášení problémů jako issue.
# (Na GitLabu dělá totéž krok „uloz“ v .gitlab-ci.yml a nastroje/issue.py.)
set -euo pipefail

# web (GitHub Pages z větve main): akce rozdělené po týdnech + mapová knihovna
rm -f data/t-*.json data/prehled.json data/prubezne.json
python nastroje/rozdel.py data
[ -f vendor/leaflet/leaflet.js ] || python nastroje/leaflet.py vendor/leaflet

git config user.name "kulturni-vlozky-bot"
git config user.email "kulturni-vlozky-bot@users.noreply.github.com"
git add -A data vendor
if git diff --cached --quiet; then
  echo "beze změn"
else
  git commit -q -m "Data $(TZ=Europe/Prague date +%F)"
  for i in 1 2 3; do
    { git pull -q --rebase -X theirs origin main || { git rebase --abort 2>/dev/null; false; }; } \
      && git push -q origin HEAD:main && break
    [ "$i" = 3 ] && exit 1
    sleep 15
  done
fi

# problémy se zdroji -> jedno issue „Problém se zdroji“ (přijde e-mail); když vše funguje, zavře se
NAZEV="Problém se zdroji"
CISLO=$(gh issue list --state open --search "\"$NAZEV\" in:title" --json number --jq '.[0].number // empty')
if [ -s data/problemy.md ]; then
  if [ -n "$CISLO" ]; then gh issue comment "$CISLO" --body-file data/problemy.md
  else gh issue create --title "$NAZEV" --body-file data/problemy.md; fi
elif [ -n "$CISLO" ]; then
  gh issue close "$CISLO" --comment "Všechny zdroje zase fungují."
fi
