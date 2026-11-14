"""Rock Café – seznam akcí po měsících (/cs/program/ a /cs/program/RRRR/MM)."""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cas, cisty

TYPY = {"hudba": "koncert", "koncert": "koncert", "divadlo": "divadlo", "film": "film", "kino": "film",
        "prednaska": "prednaska", "beseda": "prednaska", "talkshow": "prednaska", "vystava": "vystava",
        "tanec": "tanec", "party": "spolecenska"}


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for a in s.select("a.list-item"):
            h = a.find("h2")
            d = a.select_one(".date")
            if not h or not d:
                continue
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", d.get_text())
            if not m:
                continue
            datum = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            c = cas(d.get_text().split(",", 1)[1] if "," in d.get_text() else "")
            nazev = cisty(h.get_text())
            if (nazev, datum, c) in videno:
                continue
            videno.add((nazev, datum, c))
            druh = bez_diakritiky(cisty(a.select_one(".type").get_text())).lower() if a.select_one(".type") else ""
            vysledek.append(akce(
                nazev=nazev, datum=datum, cas=c, misto="Rock Café", url=a.get("href"),
                typ=TYPY.get(druh), znacky=druh or None,
            ))
    return vysledek
