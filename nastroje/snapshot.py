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
UA = "Mozilla/5.0 (X11; Linux x86_64) KulturniVlozky/0.1 (+https://github.com/m-tomasek/kulturni-vlozky)"

# Doplňkové adresy jen pro průzkum (hotové kalendářové exporty apod.)
PRUZKUM = {
    "improliga-ical": "https://improliga.cz/kalendar-predstaveni/?ical=1",
    "improliga-api": "https://improliga.cz/wp-json/tribe/events/v1/events?per_page=50",
    "improliga-feed": "https://improliga.cz/feed/",
    "alta-program": "https://www.altart.cz/program/",
    "alta-goout": "https://goout.net/cs/studio-alta/vzwnn/events/",
    "alfred-program": "https://www.alfredvedvore.cz/program/",
    "hrdinu-cs": "https://studiohrdinu.cz/program/",
}


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
    for z in cfg["zdroje"]:
        for i, u in enumerate(z["urls"]):
            ulohy.append((f"{z['id']}-{i}", rozbal(u, dnes)))
    ulohy += list(PRUZKUM.items())
    for nazev, url in ulohy:
        try:
            kod, obsah = stahni(url)
            pripona = "json" if url.endswith("per_page=50") else "html"
            if "ical" in nazev:
                pripona = "ics"
            if "feed" in nazev:
                pripona = "xml"
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
