# Kulturní vložky

Přehled akcí menších pražských scén na jednom místě. Každé ráno je sbírají
skripty v GitHub Actions, výsledek je na stránce **https://m-tomasek.github.io/kulturni-vlozky/**.

## Co kde je

| Soubor | K čemu |
|---|---|
| `zdroje.yml` | seznam sledovaných webů (dá se upravit přímo v prohlížeči na GitHubu) |
| `pravidla.yml` | co se vynechává (dětské, zadáno, pro školy…) a jak se akce třídí do typů |
| `scrapers/` | jeden skript na každý web |
| `run.py` | denní běh: sběr, sloučení, změny, zrušené akce |
| `data/akce.json` | aktuální akce (zároveň paměť systému) |
| `data/zdravi.json` | který zdroj kdy naposledy fungoval |
| `index.html` | dashboard |

## Jak to funguje

- **Každé ráno** (workflow *Denní sběr akcí*) se stáhnou programy, odfiltrují se dětské a uzavřené akce
  a akce mimo Prahu, sloučí se duplicity (web pořadatele má přednost před agregátory) a porovnají se s minulým během:
  - nová akce dostane štítek **nové**,
  - změna času, místa nebo dostupnosti vstupenek se zobrazí jako **⚠ změna**,
  - akce, která ze zdroje zmizí, je druhý den **zrušeno?** a třetí den zmizí i odsud
    (pokud se zdroj ten den nenačetl, nic se nesoudí).
- **Když se nějaký web rozbije** (vrátí 0 akcí nebo výrazně méně než minule), založí se issue
  „Problém se zdroji“ a přijde e-mail. Opravu stačí zadat Claudovi.

## Nový zdroj

Napiš Claudovi „přidej zdroj …“. Workflow *Snapshot zdrojů* (ruční spuštění) stáhne stránky a nabídne je ke stažení
jako dočasný soubor (nejsou v repu), podle nich se napíše scraper.
