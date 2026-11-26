# CLAUDE.md – kulturni-vlozky

Úplná pravidla a mapa všech repozitářů: **m-tomasek/datasety/CLAUDE.md** (soukromý repozitář).

## Co repozitář dělá
- **Veřejný.** Kulturní program v Praze: weby scén (`scrapers/`, jeden skript na web, seznam v `zdroje.yml`) + GoOut.
  `run.py` stáhne, odfiltruje (`pravidla.yml`), sloučí duplicity a porovná s minulým během (nové / změna / zrušeno?).
- Data: `data/akce.json` (zároveň paměť změn), `data/zdravi.json`, `data/mista.json`; `nastroje/rozdel.py` dělí akce po týdnech
  (`data/t-*.json`). Web `index.html` na GitHub Pages z `main`: https://m-tomasek.github.io/kulturni-vlozky/
- Běhy (`.github/workflows/`): `sber.yml` denně 4:13 UTC, `hlidac.yml` denně 11:37 UTC (dosběr chybných zdrojů + data
  starší 30 h = issue), `snapshot.yml` ručně (stáhne stránky z `nastroje/pruzkum.txt` do artefaktu a větve `ladeni-raw`).
  Ukládání a issue „Problém se zdroji“ dělá `nastroje/github_uloz.sh`.
- Testy: `python -m unittest discover -s tests` (bez internetu, běží před každým sběrem). Lokálně: `pip install -r requirements.txt`,
  `python run.py` (nebo `--jen id1,id2`, `--jen-chybne`).
- Závislosti: `requirements.txt` (pevné verze), Leaflet v `vendor/` (`nastroje/leaflet.py`). Žádné secrety, jen `github.token`.
- **Druhá kopie na GitLabu** (`gitlab.com/michal.tomasek/kulturni-vlozky`, `.gitlab-ci.yml`, proměnná `PROJEKT_TOKEN`):
  stejný kód, vlastní data a web. Změny kódu se nahrávají do obou; data si každá kopie ukládá sama.
  Architektura a kompromisy: `docs/ADR-001-architektura.md`.

## Zvláštnosti a rizika
- **Veřejný repozitář:** nikdy necommitovat hesla, tokeny ani osobní údaje; data z `datasety` sem nepatří.
- Commit dat dělá bot s `git pull --rebase -X theirs` (3 pokusy); `concurrency: zapis-do-repa` hlídá souběh sběru a hlídače.
- Nový zdroj = soubor v `scrapers/` + řádek v `zdroje.yml`; vypnutí `aktivni: false`. Pro průzkum použít `snapshot.yml`.
- Cizí weby mívají krátké výpadky – hlásit až druhý den po sobě (už to tak funguje), nezvyšovat počet pokusů ani tempo.

## Výtah společných pravidel
1. Jsem vlastník, ne programátor: nejjednodušší řešení, vše česky, ke každému PR krátký popis pro laika;
   u všeho, co mám udělat já, přímý odkaz a co přesně kam vložit.
2. Žádný plánovaný běh častěji než 1× denně (pravidlo z `datasety/README.md`).
3. Šetrné stahování: bez proxy, střídání IP a předstírání prohlížeče; respektovat robots.txt; malé tempo s náhodnou
   odchylkou; při 429 čekat, při 403 zdroj pozastavit a založit issue; stahovat jen nové nebo změněné.
4. Osobní údaje fyzických osob neukládat (pravidlo z `datasety`; README tohoto repozitáře ho zatím neuvádí).
5. Rozpočet Actions za účet 2 000 min/měsíc, cíl pod 1 000. Tento repozitář je veřejný, jeho minuty se nepočítají,
   ale rozvrhy držet úsporné.
6. Každá změna = větev `navrh/<téma>` + pull request; před sloučením zkušební běh (*Run workflow*, i jen pro vybrané zdroje).
7. Zeptat se před: novým secretem, mazáním, změnou rozvrhu, vyšší spotřebou minut, změnou zasahující GitLab kopii či jiný repozitář.
8. Když se změní pravidla nebo rozvrh, upravit v témže PR i tento soubor a `datasety/CLAUDE.md`.
