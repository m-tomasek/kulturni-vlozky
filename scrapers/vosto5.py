import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for mesic_blok in s.select("div.program-month"):
            h = mesic_blok.find("h3")
            rok = re.search(r"(20\d\d)", h.get_text()) if h else None
            for it in mesic_blok.select("li.program-item"):
                d = it.select_one(".program-day")
                m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", d.get_text() if d else "")
                if not m:
                    continue
                datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
                if rok and datum.year != int(rok.group(1)):
                    datum = datum.replace(year=int(rok.group(1)))
                t = it.select_one(".program-time")
                nazev = cisty(it.select_one(".program-title").get_text())
                venue = cisty(it.select_one(".program-venue").get_text()) if it.select_one(".program-venue") else ""
                hlavicka = it.select_one("a.program-header")
                rez = it.select_one("a.program-reservation-link")
                zajezd = "ZÁJEZD" in nazev.upper()
                mimo = zajezd or (venue and "praha" not in bez_diakritiky(venue).lower())
                vysledek.append(akce(
                    nazev=re.sub(r"\s*ZÁJEZD\s*", " ", nazev), datum=datum,
                    cas=cas(t.get_text()) if t else None,
                    misto=f"Vosto5 – {venue}" if venue else "Vosto5",
                    url=hlavicka["href"] if hlavicka else None,
                    vstupenky=rez["href"] if rez else None,
                    stav="neznamo", typ="divadlo", mimo_prahu=mimo,
                ))
    return vysledek
