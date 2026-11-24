"""ColosseumTicket – prodej vstupenek (divadla, koncerty, muzikály) – agregátor jako GoOut.

Data z API webu: /api/title?locale=cs&categorySlug=…&size=100&from=… (stránkování po 100 titulech).
Každý titul má seznam termínů (events) s místem a městem; bere se jen Praha.
Kategorie prohlídky, kino, sport se nečtou (prohlídky mají tisíce časů po čtvrthodinách).
Kategorie a štítky jdou do značek, takže pravidla (pro děti…) platí i tady.
"""
import datetime as dt
import json

from .spolecne import akce

API = "https://www.colosseumticket.cz/api/title?locale=cs&categorySlug={kat}&size={size}&from={od}&dateFrom={d1}&dateTo={d2}"
WEB = "https://www.colosseumticket.cz/cs/akce/"
KATEGORIE = ["divadlo", "hudba", "muzikal", "festival", "ostatni"]
TYPY = {"divadlo": "divadlo", "hudba": "koncert", "muzikal": "divadlo", "festival": "festival"}
SIZE = 100


def ziskej(stahni, zdroj, dnes):
    konec = dnes + dt.timedelta(days=int(zdroj.get("dni") or zdroj.get("_horizont") or 60))
    vysledek, videno = [], set()
    for kat in zdroj.get("kategorie") or KATEGORIE:
        od = 0
        while True:
            d = json.loads(stahni(API.format(kat=kat, size=SIZE, od=od, d1=dnes.isoformat(), d2=konec.isoformat())))
            tituly = d.get("data") or []
            for t in tituly:
                kategorie = [k.get("slug") for k in t.get("category") or []]
                if not kategorie or set(kategorie) <= {"prohlidky", "kino", "sport", "pro-deti"}:
                    continue
                znacky = ", ".join([k.get("title") for k in t.get("category") or []] +
                                   [s.get("title") for s in t.get("tags") or []][:6])
                typ = next((TYPY[k] for k in kategorie if k in TYPY), None)
                for e in t.get("events") or []:
                    v = e.get("venue") or {}
                    # stejné představení bývá prodávané pod dvěma tituly (česky / anglicky) – stačí jednou
                    if ((v.get("municipality") or {}).get("title") or "") != "Praha" or e.get("id") in videno \
                            or (v.get("title"), e.get("start")) in videno:
                        continue
                    try:
                        zac = dt.datetime.fromisoformat(e["start"])
                    except (KeyError, ValueError):
                        continue
                    if not (dnes <= zac.date() <= konec):
                        continue
                    videno.update([e.get("id"), (v.get("title"), e.get("start"))])
                    kon = dt.datetime.fromisoformat(e["end"]) if e.get("end") else None
                    pmin, pmax = e.get("priceMin"), e.get("priceMax")
                    cena = (f"{pmin}–{pmax} Kč" if pmin and pmax and pmin != pmax else f"{pmin or pmax} Kč") \
                        if (pmin or pmax) else None
                    a = akce(nazev=t.get("title") or "", datum=zac.date(), cas=zac.strftime("%H:%M"),
                             konec_cas=kon.strftime("%H:%M") if kon and kon.date() == zac.date() else None,
                             misto=v.get("title"), url=f"{WEB}{t['id']}-{t.get('slug', '')}", typ=typ, cena=cena,
                             stav="zruseno" if e.get("cancelled") else "vyprodano" if e.get("vacancies") == 0 else "neznamo",
                             popis=t.get("claim"), znacky=znacky)
                    gps = v.get("gps") or {}
                    if gps.get("latitude") and gps.get("longitude"):
                        a["poloha"] = [round(gps["latitude"], 4), round(gps["longitude"], 4)]
                    if a["nazev"]:
                        vysledek.append(a)
            od += SIZE
            if len(tituly) < SIZE or od >= (d.get("count") or 0) or od >= 3000:
                break
    return vysledek
