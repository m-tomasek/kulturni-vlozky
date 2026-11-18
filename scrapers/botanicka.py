"""Botanická zahrada hl. m. Prahy (Troja) – článek „Program akcí a výstav“.

Akce jsou v článku jako odkazy s datem v textu: „Křišťálová zahrada 27. 11. 2026–14. 2. 2027“,
„Svatomartinský přípitek ve Vinotéce sv. Kláry 11. 11. 2026“.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cisty

DATUM = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)?\s*(?:[–-]\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d))?\s*$")


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        # .article_detail je na stránce víckrát (záhlaví a pak tělo článku) – projdou se všechny
        for a in s.select(".article_detail p a[href]") or s.select("p a[href]"):
            t = cisty(a.get_text(" "))
            m = DATUM.search(t)
            if not m:
                continue
            d1, m1, r1, d2, m2, r2 = m.groups()
            r1 = int(r1 or r2 or dnes.year)
            try:
                od = dt.date(r1, int(m1), int(d1))
                do = dt.date(int(r2), int(m2), int(d2)) if d2 else None
            except ValueError:
                continue
            nazev = cisty(t[:m.start()]).rstrip(" –-,")
            if not nazev or (nazev, od) in videno:
                continue
            videno.add((nazev, od))
            vysledek.append(akce(nazev=nazev, datum=od, konec_datum=do if do and do != od else None,
                                 misto="Botanická zahrada Praha (Troja)", url=a["href"],
                                 typ="vystava" if do else None))
    return vysledek
