"""Botanická zahrada PřF UK (Na Slupi) – stránka „Kalendář akcí“ (bz-uk.cz/cs/kalendar).

Kalendář je jeden odstavec za druhým: <strong>14. 5. – 27. 9.</strong><br/> <a>Název</a> (popis)<br/>
<strong>17. 5.</strong><br/> Botanická burza<br/>… Rok u dat není – je to program na jednu sezónu,
rok se vezme z textu stránky (první „20xx“), jinak letošní.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup, NavigableString

from .spolecne import akce, cisty

MISTO = "Botanická zahrada PřF UK (Na Slupi)"
URL = "https://www.bz-uk.cz/cs/kalendar"


def _rozsah(text, rok):
    t = cisty(text)
    m = re.fullmatch(r"(\d{1,2})\.\s*(?:(\d{1,2})\.\s*)?(?:[–-]\s*(\d{1,2})\.\s*(\d{1,2})\.)?", t)
    if not m:
        return None, None
    d1, m1, d2, m2 = m.groups()
    try:
        if d2:
            do = dt.date(rok, int(m2), int(d2))
            od = dt.date(rok, int(m1 or m2), int(d1))
            return od, do
        return dt.date(rok, int(m1), int(d1)), None
    except (TypeError, ValueError):
        return None, None


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        obsah = s.select_one(".node__content") or s
        r = re.search(r"\b(20\d\d)\b", obsah.get_text(" "))
        rok = int(r.group(1)) if r else dnes.year
        for p in obsah.find_all("p"):
            if not p.find("strong"):
                continue
            aktualni, casti, odkaz = None, [], None

            def uloz():
                if aktualni and aktualni[0]:
                    nazev = cisty(" ".join(casti)).strip(" ,–-")
                    if nazev:
                        od, do = aktualni
                        vysledek.append(akce(nazev=nazev, datum=od, konec_datum=do, misto=MISTO,
                                             url=odkaz or URL, typ="vystava" if do else None))

            for el in p.children:
                if getattr(el, "name", None) == "strong":
                    uloz()
                    aktualni, casti, odkaz = _rozsah(el.get_text(" "), rok), [], None
                elif getattr(el, "name", None) == "br":
                    continue
                else:
                    txt = str(el) if isinstance(el, NavigableString) else el.get_text(" ")
                    if txt.strip():
                        casti.append(txt)
                    if getattr(el, "name", None) == "a" and el.get("href") and not odkaz:
                        odkaz = el["href"]
            uloz()
    return vysledek
