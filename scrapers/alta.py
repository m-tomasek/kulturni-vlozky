import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for it in s.select("article.schedule-item"):
            a = it.select_one(".schedule-item__title a")
            btn0 = it.select_one(".schedule-item__button")
            if not a or "/program/" not in a.get("href", "") or (btn0 and "studioalta" not in btn0.get("href", "")):
                continue  # sbírky, výzvy apod.
            d = cisty(it.select_one(".schedule-item__date").get_text(" ")) if it.select_one(".schedule-item__date") else ""
            datumy = re.findall(r"(\d{1,2})\.\s*(\d{1,2})\.", d)
            if not datumy:
                continue
            zac = odvod_rok(int(datumy[0][0]), int(datumy[0][1]), dnes)
            kon = odvod_rok(int(datumy[1][0]), int(datumy[1][1]), zac) if len(datumy) > 1 else None
            tagy = " · ".join(cisty(t.get_text()) for t in it.select(".tag__text"))
            btn = it.select_one(".schedule-item__button")
            btn_t = cisty(btn.get_text()).lower() if btn else ""
            stav = "vyprodano" if "vyprod" in btn_t else ("volno" if "vstupenk" in btn_t else "neznamo")
            perex = it.select_one(".schedule-item__excerpt")
            vysledek.append(akce(
                nazev=a.get_text(), datum=zac, cas=cas(d), konec_datum=kon if kon and kon != zac else None,
                misto="Studio ALTA", url=a["href"], vstupenky=btn["href"] if btn and stav == "volno" else None,
                stav=stav, typ="tanec", znacky=tagy or None, popis=perex.get_text(" ") if perex else None,
            ))
    return vysledek
