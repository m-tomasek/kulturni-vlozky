import datetime as dt
import unittest

import run
from scrapers import archiweb, botanicka, camp, kudyznudy, lesypraha

D = dt.date(2026, 11, 18)


class Tematicke(unittest.TestCase):
    def test_camp_vynecha_detske_a_pozna_vyprodano(self):
        h = ('<a href="/program/detail/x" class="card"><div class="card__tags"><div class="tag">pro děti</div></div>'
             '<time datetime="2026-11-25"></time><div class="card__title">Dětská</div></a>'
             '<a href="/program/detail/y" class="card"><div class="card__tags"><div class="tag">kapacita naplněna</div>'
             '<div class="tag">přednáška</div></div><time datetime="2026-11-25"></time><time datetime="19:00/22:00"></time>'
             '<div class="card__title">All You Can Read</div></a>')
        a = camp.ziskej(lambda u: h, {"urls": ["x"]}, D)
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]["cas"], a[0]["konec_cas"], a[0]["stav"], a[0]["typ"]), ("19:00", "22:00", "vyprodano", "prednaska"))

    def test_lesy_kazdy_den_zvlast(self):
        h = ('<article class="event main"><div class="headline"><h2><a href="https://lesypraha.cz/akce/v/">Věnec</a></h2></div>'
             '<div class="item date-of-event"><span class="day">24. 11. 2026</span><span class="day">25. 11. 2026</span></div>'
             '<div class="item time-of-event"><span class="from">17:00</span><span class="to"> – 19:00</span></div>'
             '<div class="item place"><a>Ekocentrum Prales</a></div></article>')
        a = lesypraha.ziskej(lambda u: h, {"urls": ["x"]}, D)
        self.assertEqual([x["datum"] for x in a], ["2026-11-24", "2026-11-25"])

    def test_kudyznudy_preskoci_trhy(self):
        h = ('<div itemscope itemtype="http://schema.org/Event"><meta itemprop="startDate" content="2026-11-21"/>'
             '<a href="/akce/a"><span itemprop="name">Za krásami Toulcova dvora</span></a></div>'
             '<div itemscope itemtype="http://schema.org/Event"><meta itemprop="startDate" content="2026-11-21"/>'
             '<a href="/akce/b"><span itemprop="name">Farmářské trhy na Náplavce</span></a></div>')
        a = kudyznudy.ziskej(lambda u: h, {"urls": ["https://www.kudyznudy.cz/kalendar-akci/priroda-a-ekologie/hlavni-mesto-praha"]}, D)
        self.assertEqual([x["nazev"] for x in a], ["Za krásami Toulcova dvora"])

    def test_archiweb_jen_praha(self):
        self.assertTrue(archiweb.je_praha("HIDDEN Holešovice"))
        self.assertTrue(archiweb.je_praha("Kruh, z.s."))
        self.assertFalse(archiweb.je_praha("Aedes Architecture Forum"))
        self.assertFalse(archiweb.je_praha("Dům umění města Brna"))

    def test_botanicka_rozsah(self):
        h = '<div class="article_detail"><p><a href="u">Křišťálová zahrada 27. 11. 2026–14. 2. 2027</a></p></div>'
        a = botanicka.ziskej(lambda u: h, {"urls": ["x"]}, D)[0]
        self.assertEqual((a["nazev"], a["datum"], a["konec_datum"]), ("Křišťálová zahrada", "2026-11-27", "2027-02-14"))

    def test_temata(self):
        self.assertEqual(run.urci_temata({"nazev": "Komentovaná prohlídka Winternitzovy vily", "typ": "jine"}), ["architektura"])
        self.assertEqual(run.urci_temata({"nazev": "Vycházka za ptáky v Troji", "typ": "jine"}), ["priroda"])
        self.assertEqual(run.urci_temata({"nazev": "Koncert Les", "typ": "koncert"}), [])
        self.assertEqual(run.urci_temata({"nazev": "Cokoli", "typ": "jine"}, "priroda"), ["priroda"])


if __name__ == "__main__":
    unittest.main()
