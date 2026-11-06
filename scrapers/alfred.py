from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import MESICE, akce, bez_diakritiky, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for p in s.select("div.performance"):
            a = p.select_one(".title a")
            if not a:
                continue
            sub = p.select_one(".subtitle")
            for tr in p.select("tr.term"):
                den = tr.select_one(".date")
                hod = tr.select_one(".hour")
                if not den or not hod:
                    continue
                mesic_slovo = bez_diakritiky(hod.get_text(" ").split()[0]).lower()
                mesic = MESICE.get(mesic_slovo)
                if not mesic or not den.get_text().strip().isdigit():
                    continue
                ikona = cisty(tr.select_one(".icon").get_text(" ")) if tr.select_one(".icon") else ""
                text = cisty(p.get_text(" ")).lower()
                stav = "vyprodano" if "vyprodáno" in (ikona.lower() or text) else "neznamo"
                znacky = " · ".join(x for x in [cisty(sub.get_text(" ")) if sub else "",
                                                "dětem" if "dětem" in text else "",
                                                "premiéra" if "premiéra" in text else "",
                                                "malá scéna" if "malá scéna" in text else ""] if x)
                vysledek.append(akce(
                    nazev=a.get_text(), datum=odvod_rok(int(den.get_text()), mesic, dnes), cas=cas(hod.get_text(" ")),
                    misto="Alfred ve dvoře", url=urljoin(url, a["href"]), stav=stav, typ="divadlo",
                    znacky=znacky or None,
                ))
    return vysledek
