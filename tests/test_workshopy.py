import datetime as dt
import unittest

import run
from scrapers import improbox, nd, obecny, textove, zp

D = dt.date(2026, 11, 24)
PR = run.priprav_pravidla({"typy": {"workshop": ["workshop", "dilna", "dilny", "kurz", "lekce"],
                                    "improvizace": ["impro"], "vystava": ["vystava"], "prednaska": ["prednaska"]}})


class Workshopy(unittest.TestCase):
    def test_zp_kalendar(self):
        h = ('<div class="courses-block"><h4>Prosinec 2026</h4><ul>'
             '<li class="status-open"><span class="zp-list-date-visible"><time>4. prosince</time></span>'
             '<a href="https://atelier9.cz/kurzy-new/skicak/"><h3>Skicák v kapse</h3></a>'
             '<div class="list-excerpt">urban sketching</div></li>'
             '<li class="status-closed"><span class="zp-list-date-visible"><time>12. prosince</time></span>'
             '<a href="/x"><h3>Arteterapie</h3></a></li>'
             '<li><span class="zp-list-date-visible"><time>7. prosince</time></span><h3>Fest Sokolov</h3></li></ul></div>')
        a = zp.ziskej(lambda u: h, {"urls": ["u"], "misto": "Ateliér 9", "vynechat": "Sokolov"}, D)
        self.assertEqual([(x["datum"], x["nazev"], x["stav"], x["typ"]) for x in a],
                         [("2026-12-04", "Skicák v kapse", "neznamo", "workshop"),
                          ("2026-12-12", "Arteterapie", "vyprodano", "workshop")])

    def test_textove_terminy_kurz_a_prihlasky(self):
        h = ("<html><body><h1>Kaligrafie</h1><p>KDY: neděle 8. 11. 2026 9:30 - 16:30 další termín 31. 1. 2027. "
             "Cena při přihlášení po 8. 10. 2026 (u lednového termínu po 31. 12. 2026).</p></body></html>")
        a = textove.ziskej(lambda u: h, {"urls": ["u"]}, D)
        self.assertEqual([(x["datum"], x["nazev"]) for x in a], [("2027-01-31", "Kaligrafie")])
        h2 = ("<html><body><h1>ND+ LAB</h1><p>Termíny workshopů: 15. 10., 29. 10., 12. 11., 26. 11., 3. 12., 10. 12., "
              "17. 12. 2026 vždy od 18:00</p></body></html>")
        a = textove.ziskej(lambda u: h2, {"urls": ["u"]}, D)
        self.assertEqual([(x["datum"], x["cas"], x["nazev"]) for x in a],
                         [("2026-11-26", "18:00", "ND+ LAB (kurz od 26. 11. do 17. 12.)")])

    def test_textove_semestr_od_do(self):
        h = ("<html><body><h1>AtVU</h1><p>ZIMNÍ KURZY od 6.10.2026 do 18.12.2026 (10 lekcí) "
             "JARNÍ KURZY od 12.1.2027 do 19.3.2027 (10 lekcí)</p></body></html>")
        a = textove.ziskej(lambda u: h, {"urls": ["u"], "bloky": "(ZIMNÍ|JARNÍ) KURZY", "nazev_akce": "Kresba"}, D)
        self.assertEqual([(x["datum"], x["nazev"]) for x in a],
                         [("2027-01-12", "Kresba – jarní kurzy (kurz od 12. 1. do 19. 3.)")])

    def test_textove_vikendovy_workshop(self):
        h = "<html><body><h1>Sandály</h1><p>Termín: pátek 19. až neděle 21. února 2027</p></body></html>"
        a = textove.ziskej(lambda u: h, {"urls": ["u"]}, D)
        self.assertEqual([x["datum"] for x in a], ["2027-02-19"])

    def test_nd_feed(self):
        x = ('<feed><entry><title>27.11.2026 16:00 - Národní divadlo - "Rusalka – operní dílna pro veřejnost"</title>'
             '<link rel="alternate" href="https://www.narodni-divadlo.cz/cs/predstaveni/rusalka?t=1"/></entry>'
             '<entry><title>25.11.2026 07:00 - Národní divadlo - "Prohlídka Národního divadla (skupiny)"</title></entry></feed>')
        a = nd.ziskej(lambda u: x, {"urls": ["u"], "vynechat": r"\(skupiny\)"}, D)
        self.assertEqual([(x["datum"], x["cas"], x["nazev"], x["misto"]) for x in a],
                         [("2026-11-27", "16:00", "Rusalka – operní dílna pro veřejnost", "Národní divadlo")])
        self.assertEqual(run.urci_typ(dict(a[0], typ=None), PR), "workshop")

    def test_improbox_rok_podle_dne(self):
        h = ('<div aria-controls="event-description-collapse"><span>Pá</span><span>27</span><span>Lis.</span>'
             '<div>Workshop</div><span>Praha</span><a href="https://fb.com/e/1">💥 Meisner</a><h3>Lektor</h3></div>'
             '<div aria-controls="event-description-collapse"><span>So</span><span>28</span><span>Lis.</span>'
             '<div>Představení</div><span>Praha</span><a href="https://fb.com/e/2">Show</a></div>'
             '<button>Zobrazit uplynulé akce</button>'
             '<div aria-controls="event-description-collapse"><span>So</span><span>1</span><span>Lis.</span>'
             '<div>Workshop</div><span>Praha</span><a href="https://fb.com/e/3">Staré</a></div>')
        a = improbox.ziskej(lambda u: h, {"urls": ["u"]}, D)
        self.assertEqual([(x["datum"], x["nazev"]) for x in a], [("2026-11-27", "Meisner")])

    def test_typ_workshop(self):
        self.assertEqual(run.urci_typ({"nazev": "Impro kurz", "typ": "workshop"}, PR), "workshop")
        self.assertEqual(run.urci_typ({"nazev": "Herecký workshop", "typ": "divadlo"}, PR), "workshop")
        self.assertEqual(run.urci_typ({"nazev": "Z dílny Josefa Lady", "typ": "vystava"}, PR), "vystava")
        self.assertEqual(run.urci_typ({"nazev": "Exkurze do lomu", "typ": None}, PR), "jine")

    def test_obecny_jen_s_textem_a_znacky(self):
        h = ('<article class="e"><span class="k">Dílna</span><span class="a">Pro dospělé</span><a class="t">Linoryt</a>'
             '<time>3. 12. 2026 (čt), 17:00</time><div class="p">Smíchov</div></article>'
             '<article class="e"><span class="k">Dílna</span><span class="a">Pro děti</span><a class="t">Malování</a>'
             '<time>3. 12. 2026 (čt), 10:00</time><div class="p">Smíchov</div></article>')
        z = {"urls": ["https://www.mlp.cz/"], "blok": "article.e", "nazev_css": "a.t", "datum": "time", "misto_css": ".p",
             "misto_predpona": "Městská knihovna – ", "znacky_css": ".k", "jen_s_textem": "Pro dospělé"}
        a = obecny.ziskej(lambda u: h, z, D)
        self.assertEqual([(x["nazev"], x["cas"], x["misto"], x["znacky"]) for x in a],
                         [("Linoryt", "17:00", "Městská knihovna – Smíchov", "Dílna")])


if __name__ == "__main__":
    unittest.main()
