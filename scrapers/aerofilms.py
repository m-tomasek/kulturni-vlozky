"""Aerofilms (distributor filmů a přenosů NT Live, Met Opera…) – stránka „Program kin“.

Stránka ukazuje týden dopředu: po dnech řádky film × kino (bez času). Bere se jen Praha.
Kina se pojmenují stejně jako u kinokinokino, aby se stejná promítání spárovala.
"""
import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .kinokinokino import jednotne_kino
from .spolecne import akce, cisty

PRENOS = re.compile(r"NT Live|Met Opera|Royal Ballet|Royal Opera|Bolšoj|přenos|divadlo", re.I)


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for den in s.select(".cinema-program__day-section"):
            h = den.select_one("h2")
            m = re.search(r"(\d{1,2})/(\d{1,2})/(20\d\d)", h.get_text(" ") if h else "")
            if not m:
                continue
            datum = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            for r in den.select(".cinema-program__row"):
                t, p = r.select_one(".cinema-program__col-title a"), r.select_one(".cinema-program__col-place")
                if not t or not p:
                    continue
                misto = cisty(p.get_text(" "))
                if not re.match(r"praha\b", misto, re.I):
                    continue
                misto = jednotne_kino(re.split(r"\s+—\s+", misto)[-1])
                nazev = cisty(t.get_text(" "))
                web = r.select_one(".cinema-program__col-ticket a[href]")
                vysledek.append(akce(nazev=nazev, datum=datum, misto=misto, url=urljoin(url, t["href"]),
                                     vstupenky=web["href"] if web else None,
                                     typ="film",
                                     znacky="přenos" if PRENOS.search(nazev) else None))
    return vysledek
