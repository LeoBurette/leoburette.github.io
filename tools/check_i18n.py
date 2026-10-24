#!/usr/bin/env python3
"""Signale les textes modifiés dans une langue mais pas dans l'autre.

Principe : à chaque validation, l'empreinte (SHA-1) de chaque paire fr/en est
mémorisée dans content/.i18n-state.json. Au contrôle suivant :

  • fr modifié, en inchangé  → ERREUR  « traduire en anglais »
  • en modifié, fr inchangé  → ERREUR  « traduire en français »
  • les deux modifiés        → OK, la paire est resynchronisée
  • longueur très déséquilibrée → avertissement (traduction oubliée ?)

Usage : python3 tools/check_i18n.py           contrôle (code 1 si erreur)
        python3 tools/check_i18n.py --accept  prend l'état actuel pour référence
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys

REPO = __file__.rsplit("/tools/", 1)[0]
CONTENT = f"{REPO}/content/content.json"
STATE = f"{REPO}/content/.i18n-state.json"

RATIO_MIN, RATIO_MAX = 0.45, 2.4      # anglais/français : au-delà, suspect


def aplatir(noeud, prefixe=""):
    for cle, val in noeud.items():
        chemin = f"{prefixe}.{cle}" if prefixe else cle
        if isinstance(val, dict) and set(val) == {"fr", "en"}:
            yield chemin, val["fr"], val["en"]
        elif isinstance(val, dict):
            yield from aplatir(val, chemin)
        else:
            raise SystemExit(f"« {chemin} » : attendu {{'fr': …, 'en': …}}, trouvé {val!r}")


def empreinte(txt):
    return hashlib.sha1(re.sub(r"\s+", " ", txt).strip().encode()).hexdigest()


def charge_etat():
    try:
        return json.load(open(STATE, encoding="utf-8"))["entries"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}


def section(chemin):
    return chemin.split(".")[0]


def main() -> int:
    paires = dict((c, (fr, en)) for c, fr, en in aplatir(
        json.load(open(CONTENT, encoding="utf-8"))))
    etat = charge_etat()
    actuel = {c: {"fr": empreinte(fr), "en": empreinte(en),
                  "frlen": len(fr), "enlen": len(en)} for c, (fr, en) in paires.items()}

    if "--accept" in sys.argv:
        cibles = [c for a in sys.argv[1:] if not a.startswith("--")
                  for c in a.split(",") if c]
        if not cibles:                        # sans clé : tout réenregistrer
            json.dump({"entries": actuel}, open(STATE, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print(f"référence enregistrée : {len(actuel)} paires fr/en")
            return 0
        inconnues = [c for c in cibles if c not in actuel]
        if inconnues:
            print("clé(s) inconnue(s) :", ", ".join(inconnues))
            for c in inconnues:
                proches = difflib.get_close_matches(c, actuel, n=3, cutoff=0.6)
                if proches:
                    print(f"  « {c} » → vouliez-vous : {', '.join(proches)} ?")
            return 2
        etat = charge_etat()
        for c in cibles:
            etat[c] = actuel[c]
        json.dump({"entries": etat}, open(STATE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"divergence acquittée pour {len(cibles)} clé(s) :")
        for c in cibles:
            print(f"  • {c}")
        print("les autres paires restent surveillées")
        return 0

    desync, ajouts, retraits, suspects = [], [], [], []
    for chemin, cur in sorted(actuel.items()):
        anc = etat.get(chemin)
        if anc is None:
            ajouts.append(chemin)
            continue
        fr_change = anc["fr"] != cur["fr"]
        en_change = anc["en"] != cur["en"]
        if fr_change and not en_change:
            desync.append((chemin, "FR modifié, EN pas mis à jour"))
        elif en_change and not fr_change:
            desync.append((chemin, "EN modifié, FR pas mis à jour"))
        # les libellés courts (« 02 — Career ») ont un écart de longueur normal
        if cur["frlen"] >= 40:
            ratio = cur["enlen"] / max(cur["frlen"], 1)
            if not (RATIO_MIN <= ratio <= RATIO_MAX):
                suspects.append((chemin, round(ratio, 2)))
    retraits = sorted(set(etat) - set(actuel))

    if desync:
        print(f"\n{len(desync)} TEXTE(S) DÉSYNCHRONISÉ(S) :\n")
        par_section = {}
        for chemin, quoi in desync:
            par_section.setdefault(section(chemin), []).append((chemin, quoi))
        for sect, items in par_section.items():
            print(f"  [{sect}]")
            for chemin, quoi in items:
                print(f"    ✗ {chemin}  — {quoi}")
    if suspects:
        print("\nLONGUEURS SUSPECTES (traduction oubliée ?) :")
        for chemin, ratio in suspects:
            print(f"    ? {chemin}  — en/fr = {ratio}")
    if ajouts:
        print(f"\n{len(ajouts)} nouvelle(s) clé(s) à relire : {', '.join(ajouts[:8])}"
              + (" …" if len(ajouts) > 8 else ""))
    if retraits:
        print(f"\n{len(retraits)} clé(s) supprimée(s) : {', '.join(retraits[:8])}"
              + (" …" if len(retraits) > 8 else ""))

    if desync:
        print("\nPour une divergence VOULUE (coquille propre à une langue, "
              "traduction impossible à aligner) :")
        print("    make ignore k=" + ",".join(c for c, _ in desync[:3]))
        print(f"\nRÉSULTAT : {len(desync)} désynchronisation(s) — corriger la langue "
              f"manquante puis relancer (la référence reste gelée d'ici là)")
        return 1

    # tout est cohérent : la référence avance (elle est gelée dès qu'une erreur apparaît)
    json.dump({"entries": actuel}, open(STATE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    if ajouts:
        print("\nRÉSULTAT : cohérent, référence mise à jour — "
              "relire les nouvelles clés")
        return 0
    print(f"\nRÉSULTAT : {len(actuel)} paires fr/en synchronisées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
