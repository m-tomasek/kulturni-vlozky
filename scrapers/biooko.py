"""Bio Oko – projekce ze strukturovaných dat (JSON-LD Event) na stránce programu."""
import datetime as dt
import html
import json

from bs4 import BeautifulSoup

from .spolecne import akce, cisty


def udalosti_jsonld(s):
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or "")
        except ValueError:
            continue
        for x in d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []:
            if isinstance(x, dict) and "Event" in str(x.get("@type")):
                yield x


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for e in udalosti_jsonld(s):
            if not e.get("startDate") or not e.get("name"):
                continue
            zac = dt.datetime.fromisoformat(e["startDate"])
            kon = dt.datetime.fromisoformat(e["endDate"]) if e.get("endDate") else None
            klic = (e.get("url"), e["startDate"])
            if klic in videno:
                continue
            videno.add(klic)
            jazyk = e.get("inLanguage")
            vysledek.append(akce(
                nazev=html.unescape(html.unescape(e["name"])), datum=zac.date(), cas=zac.strftime("%H:%M"),
                konec_cas=kon.strftime("%H:%M") if kon and kon.date() == zac.date() else None,
                misto="Bio Oko", url=e.get("url"), typ="film",
                znacky=cisty(f"{e.get('director') or ''}") or None,
                popis=f"jazyk: {jazyk}" if jazyk and jazyk not in ("cs", "sp1") else None,
            ))
    return vysledek
