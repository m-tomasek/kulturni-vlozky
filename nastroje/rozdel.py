"""Rozdělí data/akce.json na části pro web (běží při nasazení, výsledek se do repa neukládá).

Web tak nemusí stahovat všechno najednou: nejdřív si vezme přehled a nejbližší týdny, zbytek dočítá na pozadí.

  <cíl>/prehled.json   – meta, seznam částí (soubor, od, do, počet)
  <cíl>/prubezne.json  – akce trvající víc dní (výstavy, festivaly) a akce, které už začaly
  <cíl>/t-RRRR-TT.json – akce začínající v daném kalendářním týdnu
"""
import datetime as dt
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

KOREN = pathlib.Path(__file__).resolve().parent.parent


def rozdel(akce, dnes):
    """Vrátí (průběžné, {klíč týdne: [akce]}). Proběhlé akce se vynechají."""
    prubezne, tydny = [], {}
    for a in akce:
        konec = a.get("konec_datum") or a["datum"]
        if konec < dnes.isoformat():
            continue
        if a["datum"] < dnes.isoformat() or (a.get("konec_datum") and a["konec_datum"] != a["datum"]):
            prubezne.append(a)
            continue
        rok, tyden, _ = dt.date.fromisoformat(a["datum"]).isocalendar()
        tydny.setdefault(f"{rok}-{tyden:02d}", []).append(a)
    return prubezne, tydny


def zapis(cil, nazev, data):
    (cil / nazev).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    cil = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "public/data")
    cil.mkdir(parents=True, exist_ok=True)
    d = json.loads((KOREN / "data" / "akce.json").read_text(encoding="utf-8"))
    dnes = dt.datetime.now(ZoneInfo("Europe/Prague")).date()
    prubezne, tydny = rozdel(d["akce"], dnes)
    casti = []
    for klic in sorted(tydny):
        xs = tydny[klic]
        soubor = f"t-{klic}.json"
        zapis(cil, soubor, {"akce": xs})
        casti.append({"soubor": soubor, "od": min(a["datum"] for a in xs), "do": max(a["datum"] for a in xs),
                      "pocet": len(xs)})
    zapis(cil, "prubezne.json", {"akce": prubezne})
    zapis(cil, "prehled.json", {"meta": d.get("meta", {}), "prubezne": {"soubor": "prubezne.json", "pocet": len(prubezne)},
                                 "casti": casti, "celkem": len(prubezne) + sum(c["pocet"] for c in casti)})
    print(f"web: {len(casti)} týdnů + průběžné, celkem {len(prubezne) + sum(c['pocet'] for c in casti)} akcí;",
          "největší část", max([c["pocet"] for c in casti] or [0]))


if __name__ == "__main__":
    main()
