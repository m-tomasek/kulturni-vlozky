"""Kalendář kurzů ve tvaru webů Ateliér 9 a Ateliér živé pedagogiky (stejný systém „zp-list“).

Stránka /kalendar/: nadpis měsíce „Listopad 2026“, pod ním položky li s datem „1. listopadu“,
názvem (h3), krátkým popisem a lektorem. Položka s třídou status-closed má plno / uzavřenou přihlášku.
"""
import re

from bs4 import BeautifulSoup

from .spolecne import MESICE, akce, bez_diakritiky, cisty, odvod_rok
import datetime as dt


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    vynechat = re.compile(zdroj["vynechat"], re.I) if zdroj.get("vynechat") else None
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for blok in s.select(".courses-block"):
            h = blok.find(["h4", "h3", "h2"])
            m = re.search(r"(20\d\d)", h.get_text(" ") if h else "")
            rok = int(m.group(1)) if m else None
            for li in blok.select("li"):
                t, n = li.select_one(".zp-list-date-visible") or li.find("time"), li.find("h3")
                if not t or not n:
                    continue
                md = re.search(r"(\d{1,2})\.\s*([a-zA-Záčďéěíňóřšťúůýž]+)", t.get_text(" "))
                mes = MESICE.get(bez_diakritiky(md.group(2)).lower()) if md else None
                if not mes:
                    continue
                try:
                    datum = dt.date(rok, mes, int(md.group(1))) if rok else odvod_rok(int(md.group(1)), mes, dnes)
                except ValueError:
                    continue
                nazev = cisty(n.get_text(" "))
                popis = " ".join(cisty(x.get_text(" ")) for x in li.select(".list-excerpt, .calendar-excerpt"))
                if vynechat and vynechat.search(f"{nazev} {popis}"):
                    continue
                a = li.find("a", href=True)
                vysledek.append(akce(nazev=nazev, datum=datum, misto=zdroj.get("misto"), popis=popis or None,
                                     url=a["href"] if a else url, typ="workshop",
                                     stav="vyprodano" if "status-closed" in (li.get("class") or []) else "neznamo"))
    return vysledek
