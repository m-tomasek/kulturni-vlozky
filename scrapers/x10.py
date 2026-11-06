import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for art in s.select("article.performance-listed"):
            tm = art.find("time")
            if not tm or not tm.get("datetime"):
                continue
            zac = dt.datetime.fromisoformat(tm["datetime"])
            text = cisty(tm.get_text())
            konec = None
            m = re.search(r"–\s*(\d{1,2})\.\s*(\d{1,2})\.", text)
            if m:
                konec = odvod_rok(int(m.group(1)), int(m.group(2)), zac.date())
            ma_cas = re.search(r"\d{1,2}:\d{2}", text)
            a = art.select_one("h3 a")
            hlav = art.select_one(".performance-listed-header")
            listek = hlav.select_one("a") if hlav else None
            htext = cisty(hlav.get_text()).lower() if hlav else ""
            if "vyprodáno" in htext:
                stav = "vyprodano"
            elif "zrušeno" in htext:
                stav = "zruseno"
            elif listek:
                stav = "volno"
            else:
                stav = "neznamo"
            znacky = " · ".join(cisty(x.get_text()) for x in art.select(".performance-tag"))
            kdo = art.select_one(".performed-by")
            perex = art.select_one(".performance-listed-perex")
            vysledek.append(akce(
                nazev=a.get_text() if a else "", datum=zac.date(),
                cas=zac.strftime("%H:%M") if ma_cas else None, konec_datum=konec,
                misto="Divadlo X10", url=urljoin(url, a["href"]) if a else None,
                vstupenky=urljoin(url, listek["href"]) if listek else None,
                stav=stav, typ="divadlo", znacky=znacky,
                popis=" – ".join(x for x in [cisty(kdo.get_text()) if kdo else "", cisty(perex.get_text()) if perex else ""] if x),
            ))
    return vysledek
