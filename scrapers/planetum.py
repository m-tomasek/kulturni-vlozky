"""Planetum (Planetárium Praha, Štefánikova hvězdárna, Hvězdárna Ďáblice) – API e-shopu.

Pořady pro děti a školy se vynechávají podle skrytého parametru "filtrace věku"
(a podle nadtitulku "Pro děti"); ponechá se pořad, který má i jinou cílovku než děti.
"""
import datetime as dt
import json

from .spolecne import akce, bez_diakritiky, cisty

API = "https://shop.planetum.cz/web/program/?from={od}&branch=&full=1&lang=cs"
DETSKE = ("det", "zs", "ms", "rodin", "skol")
TYPY = {"projekce": "film", "prednaska": "prednaska", "porad": None}


def pro_deti(e):
    p = e.get("product") or {}
    if "det" in bez_diakritiky(p.get("beforeTitle") or "").lower():
        return True
    vek = [bez_diakritiky(x.get("value") or "").lower() for x in p.get("parameters") or []
           if "filtrace veku" in bez_diakritiky(x.get("name") or "").lower()]
    return bool(vek) and all(any(k in v for k in DETSKE) for v in vek)


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    od = dnes
    konec = dnes + dt.timedelta(days=min(zdroj.get("_horizont", 60), 60))
    for _ in range(8):
        d = json.loads(stahni(API.format(od=od.isoformat())))
        seznam = d.get("list") or []
        if not seznam:
            break
        posledni = od
        for e in seznam:
            zac = dt.datetime.fromisoformat(e["from"])
            kon = dt.datetime.fromisoformat(e["to"]) if e.get("to") else None
            posledni = max(posledni, zac.date())
            if e["id"] in videno or pro_deti(e):
                videno.add(e["id"])
                continue
            videno.add(e["id"])
            p = e.get("product") or {}
            druh = bez_diakritiky(e.get("show_type_name") or "").lower()
            vysledek.append(akce(
                nazev=cisty(p.get("title") or e["name"]), datum=zac.date(), cas=zac.strftime("%H:%M"),
                konec_cas=kon.strftime("%H:%M") if kon and kon.date() == zac.date() else None,
                misto=e.get("location_name") or "Planetum", url="https://www.planetum.cz/program/",
                typ=TYPY.get(druh), znacky=cisty(" · ".join(x for x in [e.get("show_type_name"), p.get("beforeTitle")] if x)) or None,
                popis=p.get("subTitle"),
            ))
        if posledni >= konec or posledni <= od:
            break
        od = posledni + dt.timedelta(days=1)
    return vysledek
