# Kulturní vložky

Přehled akcí pražských scén na jednom místě. Každé ráno je sbírají
skripty v GitLab CI, výsledek je na stránce **https://michal.tomasek.gitlab.io/kulturni-vlozky/**.

## Co kde je

| Soubor | K čemu |
|---|---|
| `zdroje.yml` | seznam sledovaných webů (`aktivni: false` zdroj vypne i s jeho akcemi) |
| `pravidla.yml` | co se vynechává (dětské, zadáno, pro školy…) a jak se akce třídí do typů |
| `scrapers/` | jeden skript na každý web |
| `run.py` | denní běh: sběr, sloučení, změny, zrušené akce |
| `tests/` | testy logiky (slučování, data, změny); běží před každým sběrem |
| `data/akce.json` | aktuální akce (zároveň paměť systému) |
| `data/zdravi.json` | který zdroj kdy naposledy fungoval |
| `index.html` | dashboard s filtry a mapou |
| `.gitlab-ci.yml` | plán běhu a nasazení webu |
| `docs/ADR-001-architektura.md` | proč je to postavené takhle a kde jsou limity |

## Jak to funguje

- **Každé ráno** se stáhnou programy, odfiltrují se dětské a uzavřené akce
  a akce mimo Prahu, sloučí se duplicity (web pořadatele má přednost před GoOut;
  stejný název na jiné scéně je jiná akce) a porovnají se s minulým během:
  - nová akce dostane štítek **nové**,
  - změna času, místa nebo dostupnosti vstupenek se zobrazí jako **⚠ změna**,
  - akce, která ze zdroje zmizí, je druhý den **zrušeno?** a třetí den zmizí i odsud
    (pokud se zdroj ten den nenačetl, nic se nesoudí).
- **Když se nějaký web rozbije** (vrátí 0 akcí nebo výrazně méně než minule), založí se jedno issue
  „Problém se zdroji“ a přijde e-mail; další dny se do něj jen přidává komentář a po opravě se samo zavře.
  Opravu stačí zadat Claudovi.
- **Hlídač** (druhý denní plán) selže a pošle e-mail, když jsou data starší než 30 hodin.

## Nový zdroj

Napiš Claudovi „přidej zdroj …“. Stránky se podle potřeby stáhnou ručním během s volbou `job = snapshot`
(adresy v `nastroje/pruzkum.txt`, výsledek je v artefaktech běhu) a podle nich se napíše scraper.
