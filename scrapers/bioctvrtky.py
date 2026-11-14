"""Biologické čtvrtky ve Viničné (přednášky PřF UK). Program semestru je tabulka v článku.

Čas a místo se píšou jednou v úvodním odstavci ("od 17:15 v místnosti Fotochemie ...
Viničná 7"), v tabulce je jen datum ("8. října") a řádek se jménem a názvem přednášky.
Čte se jen nejnovější článek (první na stránce kategorie).
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import MESICE, akce, bez_diakritiky, cas, cisty, odvod_rok

MISTO = "Fotochemie, Viničná 7"


def _datum(text, dnes):
    t = cisty(text)
    m = re.search(r"(\d{1,2})\.\s*([^\W\d_]+)", t)
    if m:
        mesic = MESICE.get(bez_diakritiky(m.group(2)).lower())
        if mesic:
            return odvod_rok(int(m.group(1)), mesic, dnes)
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
    return None


def ziskej(stahni, zdroj, dnes):
    url = zdroj["urls"][0]
    s = BeautifulSoup(stahni(url), "lxml")
    clanek = s.find("article") or s.find("table")
    if clanek is None:
        return []
    if clanek.name == "table":
        clanek = clanek.parent
    h = clanek.select_one("h1 a, h2 a, h3 a")
    url_clanku = urljoin(url, h["href"]) if h and h.get("href") else url

    uvod = cisty(clanek.get_text(" "))
    m = re.search(r"\bod\s+(\d{1,2}[:.]\d{2})", uvod)
    cas_prednasky = cas(m.group(1)) if m else "17:15"
    misto = MISTO

    vysledek, videno = [], set()
    for tr in clanek.select("table tr"):
        bunky = tr.find_all(["td", "th"])
        if len(bunky) < 2:
            continue
        datum = _datum(bunky[0].get_text(" "), dnes)
        if not datum:
            continue
        druha = bunky[1]
        tucne = druha.find(["strong", "b"])
        if tucne and cisty(tucne.get_text()):
            nazev = cisty(tucne.get_text())
            zbytek = cisty(druha.get_text(" ").replace(tucne.get_text(), "", 1))
        else:
            nazev, zbytek = cisty(druha.get_text(" ")), ""
        podtitul = " ".join(x for x in [zbytek] + [cisty(b.get_text(" ")) for b in bunky[2:]] if x)
        if not nazev or (nazev, datum) in videno:
            continue
        videno.add((nazev, datum))
        vysledek.append(akce(
            nazev=nazev, datum=datum, cas=cas_prednasky, misto=misto, url=url_clanku,
            typ="prednaska", popis=podtitul or None, cena="zdarma",
        ))
    return vysledek
