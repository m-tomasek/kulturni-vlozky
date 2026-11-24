import datetime as dt
import json
import unittest

import run
from scrapers import aerofilms, colosseum, kinokinokino

D = dt.date(2026, 11, 24)


class Kina(unittest.TestCase):
    def test_kinokinokino_mista_a_skolni(self):
        d = [{"program_day": "25-11-2026", "movie_name": "Milovaný", "show_time": "20:30", "location": "Světozor",
              "location2": "", "link": "https://www.kinosvetozor.cz/x", "english_friendly": "false"},
             {"program_day": "25-11-2026", "movie_name": "Fjord", "show_time": "18:00", "location": "Kino Atlas",
              "location2": "Modrý sál", "link": "", "english_friendly": "true"},
             {"program_day": "25-11-2026", "movie_name": "Školní projekce BOO", "show_time": "09:00",
              "location": "Kino Kavalírka", "location2": ""}]
        a = kinokinokino.ziskej(lambda u: json.dumps(d), {"urls": ["x"]}, D)
        self.assertEqual([(x["misto"], x["cas"], x["typ"]) for x in a],
                         [("Kino Světozor", "20:30", "film"), ("Kino Atlas – Modrý sál", "18:00", "film")])
        self.assertEqual(kinokinokino.jednotne_kino("Kino Mat"), "Kino MAT")
        self.assertEqual(kinokinokino.jednotne_kino("Cinestar Anděl"), "Cinestar Anděl")

    def test_aerofilms_jen_praha(self):
        h = ('<div class="cinema-program__day-section"><h2>Út 24/11/2026 <sup>(2)</sup></h2>'
             '<div class="cinema-program__row"><div class="cinema-program__col-title"><a href="/filmy/m/">Milovaný</a></div>'
             '<div class="cinema-program__col-place">Praha 1 — Světozor</div></div>'
             '<div class="cinema-program__row"><div class="cinema-program__col-title"><a href="/filmy/m/">Milovaný</a></div>'
             '<div class="cinema-program__col-place">Brno — Kino Art</div></div></div>')
        a = aerofilms.ziskej(lambda u: h, {"urls": ["https://www.aerofilms.cz/program-kin/"]}, D)
        self.assertEqual([(x["datum"], x["misto"], x["url"]) for x in a],
                         [("2026-11-24", "Kino Světozor", "https://www.aerofilms.cz/filmy/m/")])

    def test_colosseum_praha_vyprodano_prohlidky(self):
        praha = {"title": "Divadlo v Celetné", "municipality": {"title": "Praha"}, "gps": {"latitude": 50.08, "longitude": 14.42}}
        d = {"count": 2, "data": [
            {"id": "1", "slug": "hra", "title": "Něžná je noc", "category": [{"slug": "divadlo", "title": "Divadlo"}],
             "tags": [], "events": [
                {"id": "e1", "start": "2026-12-10T19:30:00+01:00", "end": "2026-12-10T21:15:00+01:00", "venue": praha,
                 "priceMin": 890, "priceMax": 890, "vacancies": 0},
                {"id": "e2", "start": "2026-12-11T19:30:00+01:00", "venue": {"title": "X", "municipality": {"title": "Brno"}}}]},
            {"id": "2", "slug": "p", "title": "Prohlídka", "category": [{"slug": "prohlidky", "title": "Prohlídky"}],
             "events": [{"id": "e3", "start": "2026-12-10T10:00:00+01:00", "venue": praha}]}]}
        a = colosseum.ziskej(lambda u: json.dumps(d), {"urls": ["x"], "dni": 60, "kategorie": ["divadlo"]}, D)
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]["cas"], a[0]["konec_cas"], a[0]["stav"], a[0]["cena"], a[0]["typ"]),
                         ("19:30", "21:15", "vyprodano", "890 Kč", "divadlo"))
        self.assertEqual(a[0]["url"], "https://www.colosseumticket.cz/cs/akce/1-hra")

    def test_slouceni_kina_s_vlastnim_zdrojem(self):
        oko = dict(nazev="Milovaný", datum="2026-11-25", cas="20:30", misto="Bio Oko", zdroj="biooko", stav="neznamo")
        kkk = dict(nazev="Milovaný", datum="2026-11-25", cas="20:30", misto="Bio Oko", zdroj="kinokinokino", stav="neznamo")
        aer = dict(nazev="Milovaný", datum="2026-11-25", cas=None, misto="Bio Oko", zdroj="aerofilms", stav="neznamo")
        v, _ = run.slouc({"biooko": [oko], "kinokinokino": [kkk], "aerofilms": [aer]},
                         {"biooko": "primarni", "kinokinokino": "agregator", "aerofilms": "agregator"})
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["dalsi_zdroje"], ["kinokinokino", "aerofilms"])

    def test_castecny_beh_agregator_neprebira_akci(self):
        stara = dict(id="o1", nazev="Milovaný", datum="2026-11-25", cas="20:30", misto="Bio Oko", zdroj="biooko",
                     stav="neznamo", poprve_videno="2026-11-16", zmeny=[])
        nova = dict(id="k1", nazev="Milovaný", datum="2026-11-25", cas="20:30", misto="Bio Oko", zdroj="kinokinokino",
                    stav="neznamo")
        v, stat = run.porovnej([nova], [stara], {"kinokinokino"}, D, agregatory={"kinokinokino"})
        self.assertEqual([(a["id"], a["zdroj"]) for a in v], [("o1", "biooko")])
        self.assertEqual(stat["nove"], 0)


if __name__ == "__main__":
    unittest.main()
