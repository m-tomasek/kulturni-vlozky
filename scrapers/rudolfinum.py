"""Galerie Rudolfinum – WordPress The Events Calendar, veřejné REST API (budoucí akce)."""
import datetime as dt
import html
import json
import re

from .spolecne import akce, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    url = zdroj["urls"][0]
    for _ in range(5):  # stránkování
        d = json.loads(stahni(url))
        for e in d.get("events", []):
            zac = dt.datetime.fromisoformat(e["start_date"])
            kon = dt.datetime.fromisoformat(e["end_date"]) if e.get("end_date") else None
            cely = e.get("all_day")
            venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
            misto = html.unescape(venue.get("venue") or "") or "Galerie Rudolfinum"
            if "rudolfin" not in misto.lower():
                misto = f"Galerie Rudolfinum – {misto}"
            kategorie = " · ".join(html.unescape(k.get("name", "")) for k in e.get("categories") or [])
            popis = re.sub(r"<[^>]+>", " ", html.unescape(e.get("excerpt") or e.get("description") or ""))
            vysledek.append(akce(
                nazev=html.unescape(e["title"]), datum=zac.date(), cas=None if cely else zac.strftime("%H:%M"),
                konec_datum=kon.date() if kon and kon.date() != zac.date() else None,
                konec_cas=kon.strftime("%H:%M") if kon and not cely and kon.date() == zac.date() else None,
                misto=misto, url=e.get("url"), cena=cisty(html.unescape(e.get("cost") or "")) or None,
                typ=None, znacky=kategorie or None, popis=popis,
            ))
        url = d.get("next_rest_url")
        if not url:
            break
    return vysledek
