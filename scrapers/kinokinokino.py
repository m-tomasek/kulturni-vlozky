"""kinokinokino.cz – společný program pražských artových kin (Světozor, Lucerna, Aero, Bio Oko, Ponrepo…).

Web je aplikace, data bere z jednoho souboru /data/praha/data.json (všechna promítání dopředu).
Každé promítání se zařadí ke svému kinu (pole location, případně sál/pobočka v location2).
Školní projekce se vynechávají.
"""
import datetime as dt
import json
import re

from .spolecne import akce, bez_diakritiky

# jednotné názvy kin (stejné používá i scraper Aerofilms, ať se promítání spárují)
KINA = {
    "svetozor": "Kino Světozor", "lucerna": "Kino Lucerna", "pilotu": "Kino Pilotů", "atlas": "Kino Atlas",
    "modransky": "Modřanský biograf", "evald": "Kino Evald", "bio oko": "Bio Oko", "aero": "Kino Aero",
    "ponrepo": "Kino Ponrepo", "kavalirka": "Kino Kavalírka", "mestska knihovna": "Městská knihovna (kino)",
    "mat": "Kino MAT", "edison": "Edison Filmhub", "radotin": "Kino Radotín", "kino 35": "Kino 35",
    "dlabacov": "Kino Dlabačov", "pritomnost": "Kino Přítomnost", "svepomoc": "Kino Svépomoc",
}
VYNECHAT = re.compile(r"školní projekce|projekce pro školy", re.I)


def jednotne_kino(nazev):
    """'Praha 1 — Světozor' / 'Kino Mat' / 'Aero' -> 'Kino Světozor' / 'Kino MAT' / 'Kino Aero'; jinak beze změny."""
    t = re.sub(r"\s+", " ", (nazev or "")).strip()
    n = bez_diakritiky(t).lower()
    for klic, jmeno in KINA.items():
        if re.search(rf"(?<![a-z]){klic}(?![a-z])", n):
            return jmeno
    return t


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        for p in json.loads(stahni(url)):
            nazev = (p.get("movie_name") or "").strip()
            if not nazev or VYNECHAT.search(nazev):
                continue
            try:
                datum = dt.datetime.strptime(p["program_day"], "%d-%m-%Y").date()
            except (KeyError, ValueError):
                continue
            misto = jednotne_kino(p.get("location"))
            if p.get("location2"):
                misto = f"{misto} – {p['location2']}"
            znacky = " ".join(x for x in [p.get("categories") or "",
                                          "english friendly" if p.get("english_friendly") == "true" else ""] if x)
            vysledek.append(akce(nazev=nazev, datum=datum, cas=p.get("show_time") or None, misto=misto,
                                 url=p.get("link") or "https://kinokinokino.cz/", typ="film",
                                 cena=p.get("price") or None, znacky=znacky or None))
    return vysledek
