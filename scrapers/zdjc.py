import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for it in s.select("div.event-item"):
            tm = it.select_one("time.event-date")
            if not tm:
                continue
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)", tm.get_text())
            if not m:
                continue
            datum = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            ttext = cisty(tm.get_text())
            h3 = it.find("h3")
            ps = [cisty(p.get_text()) for p in it.select(".event-details p") if cisty(p.get_text())]
            soubor = ps[0] if ps else None
            sal = ps[1] if len(ps) > 1 else None
            tl = it.select_one("a.goout-sale-button") or it.select_one("a.button")
            tl_t = cisty(tl.get_text()).lower() if tl else ""
            if "zadáno" in tl_t:
                stav = "zadano"
            elif "vyprodáno" in tl_t:
                stav = "vyprodano"
            elif "zrušeno" in tl_t:
                stav = "zruseno"
            else:
                stav = "neznamo"
            znacky = " · ".join(x for x in [soubor, "pro školy" if "škol" in ttext.lower() else None,
                                           "premiéra" if "premi" in ttext.lower() else None,
                                           "derniéra" if "derni" in ttext.lower() else None] if x)
            vysledek.append(akce(
                nazev=h3.get_text() if h3 else "", datum=datum, cas=cas(ttext),
                misto="Žižkovské divadlo J. C." + (f" – {sal}" if sal else ""),
                url=tl["href"] if tl else None, vstupenky=tl["href"] if tl else None,
                stav=stav, typ="divadlo", znacky=znacky,
            ))
    return vysledek
