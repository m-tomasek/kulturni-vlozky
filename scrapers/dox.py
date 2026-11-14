"""DOX – výpis /program: výstavy (rozsah dat) i jednotlivé akce ("18. 11. 2026, 17:30")."""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty

DATUM = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(\d{4}))?")


def rozsah(text):
    casti = DATUM.findall(text)
    if not casti:
        return None, None
    roky = [int(r) for _, _, r in casti if r]
    if not roky:
        return None, None
    data, rok = [], roky[-1]
    # rok doplníme odzadu: bez roku = stejný rok jako následující datum (nebo o rok dřív, pokud je měsíc vyšší)
    for d, m, r in reversed(casti):
        d, m = int(d), int(m)
        if r:
            rok = int(r)
        elif data and m > data[0].month:
            rok = data[0].year - 1
        try:
            data.insert(0, dt.date(rok, m, d))
        except ValueError:
            return None, None
    return data[0], (data[-1] if len(data) > 1 and data[-1] != data[0] else None)


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for b in s.select("div.entry-body"):
            a = b.select_one(".entry-title a")
            term = b.select_one(".entry-meta-term")
            if not a or not term:
                continue
            text = cisty(term.get_text(" "))
            od, do = rozsah(text)
            if not od:
                continue
            c = cas(text.split(",", 1)[1]) if "," in text else None
            misto = b.select_one(".entry-meta-place .entry-meta-value")
            popis = b.select_one(".entry-body__text")
            klic = (a["href"], od)
            if klic in videno:
                continue
            videno.add(klic)
            vysledek.append(akce(
                nazev=a.get_text(), datum=od, konec_datum=do, cas=c,
                misto=f"DOX – {cisty(misto.get_text())}" if misto and "DOX" not in misto.get_text() else "DOX",
                url=a["href"], popis=popis.get_text(" ") if popis else None,
                typ="vystava" if do and not c else None,
            ))
    return vysledek
