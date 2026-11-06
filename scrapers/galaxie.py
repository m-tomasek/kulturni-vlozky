import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok

MAX_STRAN = 8


def _hodnota(tr, trida):
    td = tr.select_one(f"td.{trida} .entry-cell__value")
    return td


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    zaklad = zdroj["urls"][0].split("?")[0]
    horizont = dnes + dt.timedelta(days=zdroj.get("_horizont", 60))
    for strana in range(1, MAX_STRAN + 1):
        url = zaklad if strana == 1 else f"{zaklad}?p0100={strana}"
        s = BeautifulSoup(stahni(url), "lxml")
        radky = s.select("tr.entry-row")
        if not radky:
            break
        posledni = None
        for tr in radky:
            dv = _hodnota(tr, "entry-meta-get_formatted_date")
            dtext = cisty(dv.get_text(" ")) if dv else ""
            m = re.search(r"(\d{1,2})/(\d{1,2})", dtext)
            if not m:
                continue
            datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
            posledni = datum
            tv = _hodnota(tr, "entry-meta-get_combined_title")
            a = tv.select_one(".title a") if tv else None
            if not a:
                continue
            klic = (a["href"], datum, dtext)
            if klic in videno:
                continue
            videno.add(klic)
            org = cisty(_hodnota(tr, "entry-meta-events_categories").get_text(" ")) if _hodnota(tr, "entry-meta-events_categories") else ""
            tagy = [cisty(x.get_text()) for x in tr.select("td.entry-meta-events_tags .entry-cell__value div")]
            sub = cisty(_hodnota(tr, "entry-meta-subname").get_text(" ")).upper() if _hodnota(tr, "entry-meta-subname") else ""
            reg = tr.select_one("td.entry-meta-registration_url a")
            if "ZRUŠENO" in sub:
                stav = "zruseno"
            elif "ZADÁNO" in sub or "zadáno" in tagy:
                stav = "zadano"
            elif "VYPRODÁNO" in sub:
                stav = "vyprodano"
            elif reg:
                stav = "volno"
            else:
                stav = "neznamo"
            casy = re.findall(r"\b\d{1,2}:\d{2}\b", dtext)
            ann = tv.select_one(".annotation")
            vysledek.append(akce(
                nazev=a.get_text(), datum=datum, cas=cas(casy[0]) if casy else None,
                konec_cas=cas(casy[1]) if len(casy) > 1 else None,
                misto=f"Stanice Galaxie ({org})" if org else "Stanice Galaxie",
                url=a["href"], vstupenky=reg["href"] if reg else None, stav=stav,
                znacky=" · ".join(tagy + ([sub.lower()] if sub else [])),
                popis=ann.get_text() if ann else None,
            ))
        if posledni and posledni > horizont:
            break
    return vysledek
