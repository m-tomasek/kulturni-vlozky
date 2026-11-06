import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty

MAX_STRAN = 8  # web sám nabízí nejvýš 8 stran po ~20 koncertech


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    zaklad = zdroj["urls"][0].split("?")[0]
    horizont = dnes + dt.timedelta(days=zdroj.get("_horizont", 120))
    for strana in range(1, MAX_STRAN + 1):
        url = zaklad if strana == 1 else f"{zaklad}?page={strana}"
        s = BeautifulSoup(stahni(url), "lxml")
        polozky = s.select("div.program-item")
        if not polozky:
            break
        posledni = None
        for it in polozky:
            a = it.select_one("h2 a")
            if not a:
                continue
            d = it.select_one("[itemprop=startDate]")
            if d and d.get("content"):
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})\D+(\d{2}):(\d{2})", d["content"])
                datum = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                t = f"{m.group(4)}:{m.group(5)}"
            else:
                dnes_el = it.select_one(".today")
                if not dnes_el:
                    continue
                datum, t = dnes, cas(dnes_el.get_text())
            posledni = datum
            href = urljoin(url, a["href"])
            if (href, datum) in videno:
                continue
            videno.add((href, datum))
            nazev = cisty(a.get_text(" "))
            zanr = it.select_one(".label-gender")
            koupit = it.select_one("form[action*='kosik']")
            text = cisty(it.get_text(" ")).lower()
            if "klub zadán" in nazev.lower():
                stav = "zadano"
            elif "vyprodáno" in text:
                stav = "vyprodano"
            elif koupit:
                stav = "volno"
            else:
                stav = "neznamo"
            perex = it.select_one(".program-item-text p")
            vysledek.append(akce(
                nazev=nazev, datum=datum, cas=t, misto="Jazz Dock", url=href,
                vstupenky=href if koupit else None, stav=stav, typ="koncert",
                znacky=zanr.get_text() if zanr else None,
                popis=perex.get_text() if perex else None,
            ))
        if posledni and posledni > horizont:
            break
    return vysledek
