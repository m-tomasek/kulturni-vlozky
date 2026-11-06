import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for it in s.select("div.s-products-text"):
            d = it.select_one(".products-date")
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(20\d\d))?", d.get_text() if d else "")
            if not m:
                continue
            datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
            if m.group(3):
                datum = datum.replace(year=int(m.group(3)))
            casy = re.findall(r"\b(\d{1,2}[.:]\d{2})\b", d.get_text()[m.end():])
            a = it.select_one("h2 a")
            misto = it.select_one(".products-place")
            typ = it.select_one(".products-type")
            perex = it.select_one(".s-products-perex")
            vysledek.append(akce(
                nazev=a.get_text() if a else "", datum=datum,
                cas=cas(casy[0]) if casy else None, konec_cas=cas(casy[1]) if len(casy) > 1 else None,
                misto="Vyšehrad" + (f" – {cisty(misto.get_text())}" if misto else ""),
                url=a["href"] if a else None, vstupenky=a["href"] if a else None,
                stav="neznamo", znacky=typ.get_text() if typ else None,
                popis=perex.get_text() if perex else None,
            ))
    return vysledek
