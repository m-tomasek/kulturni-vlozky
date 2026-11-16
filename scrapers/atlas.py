"""Kino Atlas – program z webu kina (kinoatlaspraha.cz).

Web nahrává program po dávkách přes ajax_get_program.php?date=RRRR-MM-DD. Každá dávka končí prvkem
<div class="variables" data-last-date=… data-next-cnt=…>: další dávka začíná den po data-last-date,
data-next-cnt=0 znamená konec programu. Dávka obsahuje řádky s datem ("Čt 10. 12.") a pod nimi
promítání (čas, sál, název, štítky, případně odkaz na vstupenky v GoOut).
Na web kina se program dostane dřív než na GoOut, proto vlastní čtečka.
Vynechává dětský cyklus (Dětský Atlas).
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok

ZAKLAD = "https://kinoatlaspraha.cz/"
DAVKA = ZAKLAD + "ajax_get_program.php?date={}&lang=cz&tag=&location=&searchtext="
DETSKE = {"dětský atlas", "pro děti"}


def ziskej(stahni, zdroj, dnes):
    horizont = dnes + dt.timedelta(days=int(zdroj.get("_horizont", 120)))
    vysledek, videno = [], set()
    od = dnes
    for _ in range(60):
        s = BeautifulSoup(stahni(DAVKA.format(od.isoformat())), "lxml")
        den = None
        for radek in s.select("div.line"):
            trida = radek.get("class", [])
            if "date" in trida:
                m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", cisty(radek.get_text(" ")))
                den = odvod_rok(int(m.group(1)), int(m.group(2)), dnes) if m else None
                continue
            if "event" not in trida or den is None:
                continue
            nazev_el = radek.select_one(".title")
            if not nazev_el:
                continue
            nazev = cisty(nazev_el.get_text(" "))
            stitky = [cisty(t.get("title") or t.get_text()) for t in radek.select(".tags .tag")]
            if DETSKE & {x.lower() for x in stitky}:
                continue
            koupit = radek.select_one("a.buy")
            datum = den
            if koupit and koupit.get("data-program-date"):
                try:
                    datum = dt.date.fromisoformat(koupit["data-program-date"][:10])
                except ValueError:
                    pass
            cas_el = radek.select_one(".time")
            sal = radek.select_one(".location")
            odkaz = nazev_el.select_one("a")
            cislo = re.search(r"program=(\d+)", odkaz.get("href", "")) if odkaz else None
            klic = cislo.group(1) if cislo else (nazev, datum.isoformat(), cas_el and cas_el.get_text())
            if klic in videno:
                continue
            videno.add(klic)
            cena = radek.select_one(".GoOutPrice")
            vysledek.append(akce(
                nazev=nazev, datum=datum, cas=cas(cas_el.get_text()) if cas_el else None,
                misto="Kino Atlas" + (f" – {cisty(sal.get_text())}" if sal and cisty(sal.get_text()) else ""),
                url=ZAKLAD + "?program=" + cislo.group(1) if cislo else ZAKLAD,
                vstupenky=koupit.get("href") if koupit else None,
                stav="vyprodano" if any("vyprod" in x.lower() for x in stitky) else ("volno" if koupit else "neznamo"),
                cena=f"{cisty(cena.get_text())} Kč" if cena and cisty(cena.get_text()) else None,
                typ="film", znacky=" · ".join(x for x in stitky if x) or None,
            ))
        promenne = s.select("div.variables")
        if not promenne:
            break
        p = promenne[-1]
        if p.get("data-next-cnt") in (None, "0"):
            break
        try:
            posledni = dt.date.fromisoformat((p.get("data-last-date") or "")[:10])
        except ValueError:
            break
        od = posledni + dt.timedelta(days=1)
        if od > horizont:
            break
    return vysledek
