"""Stáhne surové HTML všech zdrojů do složky raw/.

Slouží k ladění scraperů: Actions má přístup na internet, takže stránky
stáhne tam a uloží do repa, odkud je lze číst a scrapery testovat.
Spuštění: python nastroje/snapshot.py
"""
import datetime as dt
import pathlib
import re
import sys

import requests
import yaml

KOREN = pathlib.Path(__file__).resolve().parent.parent
RAW = KOREN / "raw"
UA = "Mozilla/5.0 (X11; Linux x86_64) KulturniVlozky/0.1 (+https://gitlab.com/michal.tomasek/kulturni-vlozky)"

# Doplňkové adresy jen pro průzkum: soubor nastroje/pruzkum.txt, řádek "název url".
# S parametrem --pruzkum se stahují jen tyto adresy (bez zdrojů ze zdroje.yml).
PRUZKUM = {}
_soubor = KOREN / "nastroje" / "pruzkum.txt"
if _soubor.exists():
    for _r in _soubor.read_text(encoding="utf-8").splitlines():
        if _r.strip() and not _r.startswith("#"):
            _n, _u = _r.split(None, 1)
            PRUZKUM[_n] = _u.strip()


def posun_mesic(dnes, o):
    m = dnes.month - 1 + o
    return dnes.year + m // 12, m % 12 + 1


def rozbal(url, dnes):
    def nahrad(m):
        co, posun = m.group(1), m.group(2)
        o = int(posun) if posun else 0
        rok, mesic = posun_mesic(dnes, o)
        if co == "rok":
            return str(rok)
        return f"{mesic:02d}" if co == "mesic2" else str(mesic)

    return re.sub(r"\{(rok|mesic2|mesic)(?:\+(\d+)m)?\}", nahrad, url)


def stahni(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    return r.status_code, r.content


def main():
    dnes = dt.date.today()
    RAW.mkdir(exist_ok=True)
    cfg = yaml.safe_load((KOREN / "zdroje.yml").read_text(encoding="utf-8"))
    report = []
    ulohy = []
    for z in ([] if "--pruzkum" in sys.argv else cfg["zdroje"]):
        for i, u in enumerate(z["urls"]):
            ulohy.append((f"{z['id']}-{i}", rozbal(u, dnes)))
    ulohy += list(PRUZKUM.items())
    for nazev, url in ulohy:
        try:
            kod, obsah = stahni(url)
            pripona = "json" if ("json" in nazev or url.endswith("per_page=50")) else "html"
            if "ical" in nazev:
                pripona = "ics"
            if "feed" in nazev:
                pripona = "xml"
            if nazev.endswith("-js"):
                pripona = "js"
            if "strana" in nazev:
                pripona = "txt"
            (RAW / f"{nazev}.{pripona}").write_bytes(obsah)
            report.append(f"{nazev}\t{kod}\t{len(obsah)}\t{url}")
        except Exception as e:  # noqa: BLE001
            report.append(f"{nazev}\tCHYBA\t{e}\t{url}")
    (RAW / "_report.tsv").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    sys.exit(main())
