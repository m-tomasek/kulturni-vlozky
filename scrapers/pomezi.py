import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for it in s.select("div.program-item"):
            hlavicka = it.select_one("h4.mb-3")
            if not hlavicka:
                continue
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", hlavicka.get_text())
            if not m:  # „Po celý měsíc“ apod. – stálé nabídky
                continue
            datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
            sl = hlavicka.find_parent("div")
            ps = sl.find_all("p")
            t = cas(ps[0].get_text()) if ps else None
            misto = ps[1].get_text() if len(ps) > 1 else None
            a = it.select_one("h4.mb-md-3 a")
            if not a:
                continue
            znacky = " · ".join(cisty(x.get_text()) for x in it.select("p.hs") if cisty(x.get_text()))
            box = it.select_one(".tickets-price") or it
            koupit = box.select_one("a[href*='objednat']")
            text = cisty(box.get_text(" "))
            if box.select_one(".btn-sold") or "vyprodáno" in text.lower():
                stav = "vyprodano"
            elif koupit:
                stav = "volno"
            else:
                stav = "neznamo"
            cena = re.search(r"\d[\d\s–-]*Kč", text)
            vysledek.append(akce(
                nazev=a.get_text(), datum=datum, cas=t,
                misto=f"Pomezí – {misto}" if misto else "Pomezí",
                url=urljoin(url, a["href"]),
                vstupenky=urljoin(url, koupit["href"]) if koupit else None,
                stav=stav, cena=cena.group(0) if cena else None,
                typ="divadlo", znacky=znacky,
            ))
    return vysledek
