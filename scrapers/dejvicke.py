import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString

from .spolecne import MESICE, akce, bez_diakritiky, cas, cisty


def _aktualni_mesic(s, dnes):
    """Měsíc, který stránka skutečně zobrazuje (v přepínači není odkazem)."""
    box = s.select_one("#program-mesice")
    if not box:
        return None
    for ch in box.children:
        if isinstance(ch, NavigableString):
            for slovo in re.findall(r"[a-zA-Zá-žÁ-Ž]+", str(ch)):
                mm = MESICE.get(bez_diakritiky(slovo).lower())
                if mm:
                    rok = dnes.year + (1 if mm < dnes.month - 6 else 0)
                    return rok, mm
    return None


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        rm = _aktualni_mesic(s, dnes)
        if not rm or rm in videno:  # nedostupný měsíc web nahradí aktuálním → přeskoč duplicitu
            continue
        videno.add(rm)
        rok, mesic = rm
        for blok in s.select("div.program-misto"):
            misto_nazev = blok.get("data-misto", "")
            zajezdy = "zájezd" in cisty(blok.get_text()[:200]).lower()
            for tr in blok.select("tr"):
                td = tr.find_all("td")
                if len(td) < 4:
                    continue
                den = re.search(r"\d{1,2}", td[1].get_text())
                if not den:
                    continue
                datum = dt.date(rok, mesic, int(den.group(0)))
                a = td[3].select_one("a.nazev")
                if not a:
                    continue
                pozn = td[3].find("em")
                pozn_t = cisty(pozn.get_text()) if pozn else ""
                sold = td[3].select_one("span.sold")
                sold_t = cisty(sold.get_text()).lower() if sold else ""
                listek = next((x for x in td[3].find_all("a") if "objednat" in x.get_text().lower()), None)
                bunka = cisty(td[3].get_text(" ")).lower()
                if "zrušeno" in sold_t or "zrušeno" in bunka:
                    stav = "zruseno"
                elif "vyprodáno" in sold_t:
                    stav = "vyprodano"
                elif "zadáno" in bunka and not listek:
                    stav = "zadano"
                elif listek:
                    stav = "volno"
                else:
                    stav = "neznamo"
                typ_k = "divadlo"
                if zajezdy or "zájezd" in misto_nazev.lower():
                    m = re.search(r"hrajeme v ([^)]*)", pozn_t)
                    kde = m.group(1) if m else pozn_t
                    misto = f"Dejvické divadlo na zájezdu – {kde}"
                    mimo = not re.search(r"Praha|Pražsk|Praze", kde)
                elif "Galaxie" in misto_nazev:
                    misto, mimo = "Dejvické divadlo – Galaxie (Háje)", False
                else:
                    misto, mimo = "Kavárna Dejvického divadla", False
                    typ_k = None
                vysledek.append(akce(
                    nazev=a.get_text(), datum=datum, cas=cas(td[2].get_text()), misto=misto,
                    url=urljoin("https://www.dejvickedivadlo.cz/", a["href"]),
                    vstupenky=listek["href"] if listek else None, stav=stav, typ=typ_k,
                    znacky=None if zajezdy or "zájezd" in misto_nazev.lower() else (pozn_t.strip("()") or None), mimo_prahu=mimo,
                ))
    return vysledek
