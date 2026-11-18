"""Zkouška nastavení nových zdrojů na stažených stránkách (raw/), bez zápisu dat.

nastroje/zkus.yml: seznam zdrojů ve stejném tvaru jako v zdroje.yml, navíc `soubor:` (soubor v raw/,
případně seznam souborů). Vypíše počet akcí, rozsah dat a pár ukázek -> raw/_zkus.txt.
"""
import datetime as dt
import pathlib
import sys
import traceback

import yaml
from bs4 import UnicodeDammit

KOREN = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOREN))
from run import urci_temata  # noqa: E402
from scrapers import nacti  # noqa: E402

RAW = KOREN / "raw"


def main():
    cfg = yaml.safe_load((KOREN / "nastroje" / "zkus.yml").read_text(encoding="utf-8")) or []
    dnes = dt.date.today()
    out = []
    for z in cfg:
        soubory = z["soubor"] if isinstance(z["soubor"], list) else [z["soubor"]]
        texty = []
        for s in soubory:
            f = RAW / s
            texty.append(UnicodeDammit(f.read_bytes(), ["utf-8", "windows-1250"]).unicode_markup if f.exists() else "")
        it = iter(texty)
        zz = dict(z, urls=[f"https://zkouska/{i}" for i in range(len(texty))])
        try:
            akce = nacti(z.get("scraper", z["id"])).ziskej(lambda u: next(it), zz, dnes)
        except Exception:  # noqa: BLE001
            out.append(f"## {z['id']}: CHYBA\n" + traceback.format_exc(limit=3))
            continue
        bud = [a for a in akce if (a.get("konec_datum") or a["datum"]) >= dnes.isoformat()]
        tem = [a for a in bud if urci_temata(a, z.get("tema"))]
        out.append(f"## {z['id']}: {len(akce)} akcí, budoucích {len(bud)}, s tématem {len(tem)}"
                   + (f", {min(a['datum'] for a in bud)} – {max(a['datum'] for a in bud)}" if bud else ""))
        for a in (bud or akce)[:6]:
            out.append(f"   {a['datum']} {a.get('cas') or '':5} {a['nazev'][:70]} | {(a.get('misto') or '')[:40]}"
                       f" | {urci_temata(a, z.get('tema'))}")
    (RAW / "_zkus.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
