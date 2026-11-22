import datetime as dt
import json
import unittest

from scrapers import amu, obecny

D = dt.date(2026, 11, 22)


class Skoly(unittest.TestCase):
    def test_amu_utc_misto_a_vynechani(self):
        d = {"items": [
            {"title": "Koncert", "start": "2026-11-25T17:30:00+00:00", "end": None,
             "categories": "Akce, Koncert, Sál Martinů", "url": "/cs/udalosti/k-1/"},
            {"title": "Antropocén (workshop pro pedagogy)", "start": "2026-11-23T08:00:00+00:00", "end": None,
             "categories": "ESF HAMU, Wellbeing", "url": "/x/"},
            {"title": "Výstava", "start": "2026-12-21T17:00:00+00:00", "end": "2027-01-31T17:00:00+00:00",
             "categories": "Akce, Výstava", "url": "/v/"}], "next_page": None}
        a = amu.ziskej(lambda u: json.dumps(d), {"urls": ["https://www.amu.cz/api/events/?upcoming=1"]}, D)
        self.assertEqual(len(a), 2)
        self.assertEqual((a[0]["datum"], a[0]["cas"], a[0]["typ"], a[0]["url"]),
                         ("2026-11-25", "18:30", "koncert", "https://www.amu.cz/cs/udalosti/k-1/"))
        self.assertIn("Sál Martinů", a[0]["misto"])
        self.assertEqual((a[1]["konec_datum"], a[1]["typ"]), ("2027-01-31", "vystava"))

    def test_obecny_typ_akce_a_vychozi_cas(self):
        h = '<table class="list_lec"><tr><td><strong>26. 11. 2026</strong> <em>O hvězdě</em></td></tr></table>'
        z = {"urls": ["https://www.aldebaran.cz/fyz_ctvrtky/"], "typ": "primarni", "blok": "table.list_lec td",
             "nazev_css": "em", "datum": "strong", "cas_vychozi": "16:15", "typ_akce": "prednaska"}
        a = obecny.ziskej(lambda u: h, z, D)
        self.assertEqual((a[0]["nazev"], a[0]["datum"], a[0]["cas"], a[0]["typ"]),
                         ("O hvězdě", "2026-11-26", "16:15", "prednaska"))

    def test_ics_celodenni_bez_casu(self):
        ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Výstava\nDTSTART:20261109T230000Z\n"
               "DTEND:20261130T230000Z\nEND:VEVENT\nEND:VCALENDAR\n")
        a = obecny.ziskej(lambda u: ics, {"urls": ["https://x/"], "format": "ics", "misto": "FA"}, D)
        self.assertEqual((a[0]["datum"], a[0]["cas"], a[0]["konec_datum"]), ("2026-11-10", None, "2026-11-30"))


if __name__ == "__main__":
    unittest.main()
