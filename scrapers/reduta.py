"""Reduta Jazz Club – /program-cs, položky div.progitem s data-time="RRRR-MM-DDTHH:MM"."""
import datetime as dt

from bs4 import BeautifulSoup

from .spolecne import akce, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for p in s.select("div.progitem[data-time]"):
            a = p.select_one(".progheader a") or p.select_one(".progheader")
            if not a:
                continue
            try:
                zac = dt.datetime.fromisoformat(p["data-time"])
            except ValueError:
                continue
            nazev = cisty(a.get_text())
            if not nazev or (nazev, zac) in videno:
                continue
            videno.add((nazev, zac))
            popis = p.select_one(".progaddtext")
            vysledek.append(akce(
                nazev=nazev, datum=zac.date(), cas=zac.strftime("%H:%M"), misto="Reduta Jazz Club",
                url=a.get("href") if a.name == "a" else url, popis=popis.get_text(" ") if popis else None,
                typ="koncert",
            ))
    return vysledek
