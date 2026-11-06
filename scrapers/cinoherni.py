import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        panel = s.select_one("#vse") or s  # záložka „VŠE“, ostatní záložky jsou duplicitní
        for it in panel.select("div.inscenace"):
            d = it.select_one("p.datum")
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", d.get_text() if d else "")
            if not m:
                continue
            a = it.select_one("h4 a")
            if not a:
                continue
            nazev = cisty(a.get_text(" "))
            sloupce = it.find_all("div", recursive=False)
            posl = cisty(sloupce[-1].get_text(" ")).lower() if sloupce else ""
            mimo = False
            if "zájezd" in posl:
                mimo = True
            if "vyprodáno" in posl:
                stav = "vyprodano"
            elif "zadáno" in posl:
                stav = "zadano"
            elif "zrušeno" in posl:
                stav = "zruseno"
            elif "koupit" in posl:
                stav = "volno"
            else:
                stav = "neznamo"
            vysledek.append(akce(
                nazev=nazev, datum=odvod_rok(int(m.group(1)), int(m.group(2)), dnes),
                cas=cas(d.get_text()), misto="Činoherní klub", url=a["href"],
                vstupenky=a["href"] if stav == "volno" else None,
                stav=stav, typ="divadlo", mimo_prahu=mimo,
                znacky=posl if "zájezd" in posl else None,
            ))
    return vysledek
