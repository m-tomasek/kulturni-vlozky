# ADR-001: Jak Kulturní vložky fungují a proč

**Stav:** přijato · **Datum:** 16. 11. 2026 · **Rozhoduje:** M.

## Kontext
Osobní přehled programu pražských scén pro jednoho člověka, který není programátor. Úpravy dělá Claude.
Požadavky: dostupné odkudkoli, zdarma, bez serveru, o který se někdo musí starat, a aby se dalo snadno
přidat další scénu. Od listopadu 2026 je součástí i celý GoOut, takže objem vzrostl z ~500 na ~3 000 akcí.

## Rozhodnutí
Jednou denně běží v GitLab CI dávka (`run.py`): stáhne zdroje, sloučí je, porovná s minulým během a výsledek
uloží jako soubory `data/*.json` zpět do repa. Statická stránka `index.html` si tyto soubory načte v prohlížeči.
Web se nasazuje na GitLab Pages (jen pro přihlášené členy projektu).

## Zvažované možnosti
| | A: dávka v CI + statická stránka (zvoleno) | B: server s databází (VPS) | C: naplánovaný Claude + dokument |
|---|---|---|---|
| Složitost provozu | nízká, nic neběží trvale | vysoká (aktualizace, zálohy) | nízká |
| Cena | 0 Kč (volné minuty CI) | stovky Kč měsíčně | spotřeba Claude |
| Paměť změn („nové“, „přesunuto“) | ano, v repu jako historie | ano | křehké |
| Filtry, mapa, rychlost | ano, vše v prohlížeči | ano | omezené |
| Co když služba skončí | repo jde přenést (stalo se: GitHub → GitLab) | vlastní | závislé na jednom nástroji |

## Kompromisy
- **Data v gitu** jsou zároveň databáze i záloha, ale repo roste (denně jeden commit s velkým rozdílem). Až bude
  historie vadit, stačí data přesunout do samostatné větve nebo ukládat jen artefakt.
- **Celý soubor do prohlížeče**: při ~3 000 akcích to stačí (popisy se už neposílají, seznam se kreslí po 400).
  Kolem 10 000 akcí bude potřeba dělit soubor po týdnech.
- **Jeden skript na scénu** se snadno opravuje, ale je jich přes 25 a weby se mění. Proto hlídání zdraví zdrojů
  (`data/zdravi.json`), issue s e-mailem a hlídač čerstvosti dat.
- **Slučování duplicit** mezi GoOut a weby scén je odhad podle názvu, času a místa. Když se splete, je vidět
  buď dvojice stejných akcí, nebo chybí akce se stejným názvem na jiné scéně. Pokrývají to testy v `tests/`.

## Důsledky
- Snadné: přidat scénu (jeden soubor + řádek v `zdroje.yml`), vypnout scénu (`aktivni: false`), přenést jinam.
- Těžší: cokoli „naživo“ (aktuální vyprodanost během dne) a cokoli pro víc uživatelů s vlastním nastavením.
- Hlídat: velikost `data/akce.json`, délku běhu sběru (limit 25 min), počet volných minut CI.

## Úkoly
- [x] Testy logiky spouštěné před každým sběrem
- [x] Pevné verze knihoven, mapová knihovna z vlastního webu
- [ ] Zvážit kratší historii dat v repu, až repo přesáhne stovky MB
