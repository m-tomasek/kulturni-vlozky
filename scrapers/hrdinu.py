import datetime as dt
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for li in s.select("li[itemtype$='schema.org/Event']"):
            d = li.get("data-date")
            h2 = li.select_one("h2")
            if not d or not h2:
                continue
            zac = dt.datetime.strptime(d[:16], "%Y-%m-%d %H:%M")
            a = li.select_one("a[itemprop=url]")
            # poznámky pod názvem (PREMIÉRA // VYPRODÁNO, HOST…) jsou volný text v <li>
            kopie = BeautifulSoup(str(li), "lxml")
            for x in kopie.select(".day-time, h2, a.tickets, data, meta"):
                x.decompose()
            pozn = cisty(kopie.get_text(" "))
            stav = "vyprodano" if "vyprodáno" in pozn.lower() else ("zruseno" if "zrušeno" in pozn.lower() else "neznamo")
            vysledek.append(akce(
                nazev=cisty(h2.get_text(" ")), datum=zac.date(), cas=zac.strftime("%H:%M"),
                misto="Studio Hrdinů", url=urljoin(url, a["href"]) if a else url,
                stav=stav, typ="divadlo", znacky=pozn or None,
            ))
    return vysledek
