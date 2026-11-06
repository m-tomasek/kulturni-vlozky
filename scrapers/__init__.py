"""Scrapery zdrojů. Každý modul má funkci ziskej(stahni, zdroj, dnes) -> list[dict]."""
import importlib


def nacti(zdroj_id):
    return importlib.import_module(f"scrapers.{zdroj_id}")
