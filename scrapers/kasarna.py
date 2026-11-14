"""Kasárna Karlín – dlaždice akcí na /cs/program (datum v <time datetime>, čas na stránce není)."""
import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for dl in s.select("div.node--type--event"):
            a = dl.select_one("a.tile-inside")
            t = dl.select_one("time[datetime]")
            n = dl.select_one(".event-title")
            if not a or not t or not n:
                continue
            datum = dt.date.fromisoformat(t["datetime"][:10])
            nazev = cisty(n.get_text())
            odkaz = urljoin(url, a["href"])
            if odkaz in videno:
                continue
            videno.add(odkaz)
            vst = dl.select_one("a.btn[href^=http]")
            vysledek.append(akce(
                nazev=nazev, datum=datum, cas=None, misto="Kasárna Karlín", url=odkaz,
                vstupenky=vst["href"] if vst else None, typ=None,
            ))
    return vysledek
