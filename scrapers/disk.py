import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        posledni_datum = None
        for tr in s.select("table tr"):
            td = tr.find_all("td")
            if len(td) < 4:
                continue
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", td[1].get_text())
            if m:
                posledni_datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
            t = cas(td[2].get_text())
            if not t or not posledni_datum:
                continue  # poznámky pod představením, nadpisy měsíců
            bunka = td[3]
            a = bunka.find("a")
            nazev = cisty(bunka.get_text(" "))
            if not nazev:
                continue
            posl = cisty(td[4].get_text()).upper() if len(td) > 4 else ""
            listek = td[4].find("a") if len(td) > 4 else None
            if "ZRUŠENO" in posl or "ZRUŠENO" in nazev.upper():
                stav = "zruseno"
            elif "VYPRODÁNO" in posl:
                stav = "vyprodano"
            elif listek:
                stav = "neznamo"  # prodej přes GoOut, dostupnost není vidět
            else:
                stav = "neznamo"
            vysledek.append(akce(
                nazev=nazev, datum=posledni_datum, cas=t, misto="Divadlo DISK",
                url=a["href"] if a else None,
                vstupenky=listek["href"] if listek else None,
                stav=stav, typ="divadlo",
            ))
    return vysledek
