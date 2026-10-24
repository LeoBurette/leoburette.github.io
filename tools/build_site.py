#!/usr/bin/env python3
"""Construit index.html à partir de templates/index.html et content/content.json.

`content/content.json` est la source unique des textes : chaque entrée est une
paire {"fr": …, "en": …}. Le gabarit ne contient que la structure (CSS, JS,
balisage) et des clés :

    <h1 data-key="hero.title">{{hero.title}}</h1>   →  <h1 data-key="hero.title"
                                                         data-en="…">Texte FR</h1>
    {{!meta.title.fr}}                              →  valeur échappée (attribut)

Usage : python3 tools/build_site.py [--check]
        --check : n'écrit rien, sort en erreur si une clé manque.
"""
from __future__ import annotations

import html
import json
import re
import sys

REPO = __file__.rsplit("/tools/", 1)[0]
TPL = f"{REPO}/templates/index.html"
CONTENT = f"{REPO}/content/content.json"
OUT = f"{REPO}/index.html"

BANNIERE = """<!--
  ⚠ FICHIER GÉNÉRÉ — ne pas modifier le texte ici.
  Textes  : content/content.json   (français ET anglais)
  Structure : templates/index.html
  Reconstruire : python3 tools/build_site.py   (ou `make`)
-->
"""


def aplatir(noeud, prefixe=""):
    """(chemin, fr, en) pour chaque paire {fr, en}."""
    for cle, val in noeud.items():
        chemin = f"{prefixe}.{cle}" if prefixe else cle
        if isinstance(val, dict) and set(val) == {"fr", "en"}:
            yield chemin, val["fr"], val["en"]
        elif isinstance(val, dict):
            yield from aplatir(val, chemin)
        else:
            raise SystemExit(f"valeur inattendue à « {chemin} » : {val!r}")


def main() -> int:
    paires = dict((c, (fr, en)) for c, fr, en in aplatir(
        json.load(open(CONTENT, encoding="utf-8"))))
    tpl = open(TPL, encoding="utf-8").read()
    manquants, utilises = [], set()

    # 1. placeholders échappés (attributs, <head>, JS) — langue explicite .fr/.en
    def echappe(m):
        chemin = m.group(1)
        base = chemin[:-3] if chemin.endswith((".fr", ".en")) else chemin
        utilises.add(base)
        if base not in paires:
            manquants.append(chemin)
            return m.group(0)
        return html.escape(paires[base][0 if chemin.endswith(".fr") else 1], quote=True)

    sortie = re.sub(r"\{\{!([^{}]+)\}\}", echappe, tpl)

    # 2. placeholders bruts (corps HTML, peut contenir du balisage)
    def brut(m):
        chemin = m.group(1)
        utilises.add(chemin)
        if chemin not in paires:
            manquants.append(chemin)
            return m.group(0)
        return paires[chemin][0]

    sortie = re.sub(r"\{\{(?!\!)([^{}]+)\}\}", brut, sortie)

    # 3. attribut data-en sur chaque élément à clé (traduction de bascule)
    def ajoute_en(m):
        debut, attrs, cle = m.group(1), m.group(2), m.group(3)
        if cle not in paires:
            manquants.append(cle)
            return m.group(0)
        return f'{debut}{attrs} data-en="{html.escape(paires[cle][1], quote=True)}"'

    sortie = re.sub(r'(<\w+)((?:[^>]*?)?\sdata-key="([^"]+)")', ajoute_en, sortie)

    if manquants:
        print("CLÉS MANQUANTES dans content.json :", sorted(set(manquants)))
        return 1
    if "{{" in sortie:
        reste = sortie[sortie.index("{{"):][:80]
        print("PLACEHOLDER NON RÉSOLU :", reste)
        return 1

    inutilisees = set(paires) - utilises
    if inutilisees:
        print("⚠ clés du contenu sans usage dans le gabarit :", sorted(inutilisees))

    # le doctype doit rester la première chose du fichier (sinon mode quirks)
    if sortie.lstrip().lower().startswith("<!doctype"):
        i = sortie.lower().index("<!doctype")
        fin = sortie.index(">", i) + 1
        sortie = sortie[:fin] + "\n" + BANNIERE + sortie[fin:]
    else:
        sortie = BANNIERE + sortie
    if "--check" in sys.argv:
        print(f"OK  {len(paires)} paires fr/en, gabarit cohérent (rien écrit)")
        return 0
    # filet : si index.html avait été modifié à la main, on le sauvegarde avant
    # de l'écraser (le fichier est généré, toute retouche manuelle doit passer
    # par content/content.json).
    try:
        ancien = open(OUT, encoding="utf-8").read()
    except OSError:
        ancien = None
    if ancien is not None and ancien != sortie:
        import datetime
        import shutil
        sauv = f"/tmp/index-ecrase-{datetime.datetime.now():%Y%m%d-%H%M%S}.html"
        shutil.copy2(OUT, sauv)
        print(f"⚠ index.html contenait une version différente (édition manuelle ?)")
        print(f"  sauvegarde : {sauv}")

    open(OUT, "w", encoding="utf-8").write(sortie)
    print(f"OK  index.html reconstruit — {len(paires)} paires fr/en, {len(sortie)/1024:.1f} Ko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
