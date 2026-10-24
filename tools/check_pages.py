#!/usr/bin/env python3
"""Contrôle avant publication GitHub Pages : chemins, ressources, rendu.

Sort en code 1 dès qu'un contrôle échoue, pour être utilisable en pré-commit
ou en CI. Aucun build : le site est un unique index.html + une image.
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import socketserver
import sys
import threading
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765
CHROME = ("/Users/leoburette/Library/Caches/ms-playwright/chromium_headless_shell-1228/"
          "chrome-headless-shell-mac-arm64/chrome-headless-shell")

fails: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    print(("  OK   " if ok else "  FAIL ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:   # bruit inutile en test
        pass


class Server(socketserver.TCPServer):
    allow_reuse_address = True

    def handle_error(self, request: object, client_address: object) -> None:
        """Une connexion coupée par le navigateur n'est pas une erreur de test."""
        pass


def serve() -> socketserver.TCPServer:
    handler = functools.partial(Quiet, directory=REPO)
    srv = Server(("127.0.0.1", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def fetch(path: str) -> object:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=10) as r:
            return r.status
    except Exception as exc:                        # noqa: BLE001 — on veut le détail
        return f"ERREUR {exc}"


def main() -> int:
    html = open(f"{REPO}/index.html", encoding="utf-8").read()

    # 1. ressources locales : présentes, casse exacte (Pages tourne sous Linux)
    refs = sorted({u.split("#")[0].split("?")[0]
                   for u in re.findall(r'(?:src|href)="([^"]+)"', html)
                   if not u.startswith(("http", "mailto:", "tel:", "#", "data:"))})
    absents = [r for r in refs if not os.path.exists(os.path.join(REPO, r))]
    check("ressources locales présentes, casse exacte", not absents,
          ", ".join(refs) if not absents else f"introuvables : {absents}")

    # 2. aucun chemin absolu : le site doit marcher depuis n'importe quel préfixe
    absolus = re.findall(r'(?:src|href)="(/(?!/)[^"]*|file:[^"]*)"', html)
    check("aucun chemin absolu ni file://", not absolus, absolus)

    # 3. tous les liens internes ont une cible
    ancres = set(re.findall(r'href="#([\w-]+)"', html))
    cibles = set(re.findall(r'id="([\w-]+)"', html))
    check("chaque ancre interne a sa cible", ancres <= cibles, sorted(ancres - cibles))

    # 4. serveur HTTP local = comportement Pages
    srv = serve()
    codes = {p: fetch(p) for p in ["/"] + [f"/{r}" for r in refs]}
    check("toutes les ressources répondent 200", all(v == 200 for v in codes.values()), codes)

    # 5. rendu réel depuis http://
    from playwright.sync_api import sync_playwright

    erreurs: list = []
    vues: dict = {}

    def rendu(b, label: str, w: int, h: int, mobile: bool) -> None:
        page = b.new_page(viewport={"width": w, "height": h},
                          device_scale_factor=2, is_mobile=mobile, has_touch=mobile)
        page.on("console", lambda m: erreurs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
        page.wait_for_timeout(700)
        vues[label] = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth")
        page.close()

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        rendu(b, "ordinateur", 1440, 950, False)
        rendu(b, "mobile", 390, 844, True)
        b.close()
    check("aucun débordement horizontal (ordinateur, mobile)", not any(vues.values()), vues)
    check("aucune erreur console", not erreurs, erreurs[:3])

    srv.shutdown()
    print("\nRÉSULTAT :", "prêt pour GitHub Pages" if not fails else "ÉCHEC — " + " ; ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
