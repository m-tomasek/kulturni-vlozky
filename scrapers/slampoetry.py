"""Slam poetry CZ – veřejný Google kalendář, ze kterého si program bere slampoetry.cz/c/program.

Čte se iCal export kalendáře (bez klíče). Berou se jen akce v Praze (podle místa nebo názvu).
"""
import datetime as dt
import re
from zoneinfo import ZoneInfo

from .spolecne import akce, bez_diakritiky, cisty

PRAHA = ZoneInfo("Europe/Prague")


def _rozbal(text):
    """Řádky iCal: pokračovací řádek začíná mezerou; vrací seznam (název, parametry, hodnota)."""
    radky = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    for r in radky:
        if ":" not in r:
            continue
        hlava, hodnota = r.split(":", 1)
        nazev, _, parametry = hlava.partition(";")
        yield nazev.upper(), parametry, hodnota


def _text(h):
    for co, cim in (("\\n", " "), ("\\N", " "), ("\\,", ","), ("\\;", ";"), ("\\\\", "\\")):
        h = h.replace(co, cim)
    return cisty(h)


def _cas(parametry, hodnota):
    """Vrátí (datum, 'HH:MM' nebo None)."""
    if "VALUE=DATE" in parametry.upper() or len(hodnota) == 8:
        return dt.datetime.strptime(hodnota[:8], "%Y%m%d").date(), None
    d = dt.datetime.strptime(hodnota[:15], "%Y%m%dT%H%M%S")
    if hodnota.endswith("Z"):
        d = d.replace(tzinfo=dt.timezone.utc).astimezone(PRAHA)
    else:
        m = re.search(r"TZID=([^;:]+)", parametry)
        try:
            d = d.replace(tzinfo=ZoneInfo(m.group(1))).astimezone(PRAHA) if m else d
        except Exception:  # noqa: BLE001 – neznámá zóna: bereme čas, jak je
            pass
    return d.date(), d.strftime("%H:%M")


def v_praze(e):
    t = bez_diakritiky(f"{e.get('LOCATION', '')} {e.get('SUMMARY', '')}").lower()
    return bool(re.search(r"\bpra(ha|ze|hy|gue)\b", t))


def ziskej(stahni, zdroj, dnes):
    vysledek, e = [], None
    for nazev, par, hod in _rozbal(stahni(zdroj["urls"][0])):
        if nazev == "BEGIN" and hod == "VEVENT":
            e = {}
        elif nazev == "END" and hod == "VEVENT" and e is not None:
            if e.get("DTSTART") and e.get("SUMMARY") and e.get("STATUS") != "CANCELLED" and v_praze(e):
                datum, c = e["DTSTART"]
                kd, kc = e.get("DTEND") or (None, None)
                if c is None and kd:  # celodenní: konec je v iCal „den po“
                    kd -= dt.timedelta(days=1)
                misto = _text(e.get("LOCATION", "")).split(",")[0] or "Praha"
                vysledek.append(akce(
                    nazev=_text(e["SUMMARY"]), datum=datum, cas=c,
                    konec_datum=kd if kd and kd > datum and (kd - datum).days < 14 else None,
                    konec_cas=kc if kc and kd == datum else None,
                    misto=misto, url=zdroj.get("web") or zdroj["urls"][0], typ=None,
                    znacky="slam poetry", popis=_text(e.get("DESCRIPTION", "")),
                ))
            e = None
        elif e is not None:
            if nazev in ("DTSTART", "DTEND"):
                try:
                    e[nazev] = _cas(par, hod)
                except ValueError:
                    pass
            elif nazev in ("SUMMARY", "LOCATION", "DESCRIPTION", "STATUS"):
                e[nazev] = hod
    return vysledek
