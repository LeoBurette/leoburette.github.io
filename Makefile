# Site — commandes utiles
# `make` par défaut : reconstruit index.html puis vérifie tout.

PY := python3

.PHONY: all build check i18n accept ignore pages serve clean

all: build check

build:            ## reconstruit index.html depuis content/ + templates/
	@$(PY) tools/build_site.py

i18n:             ## vérifie que français et anglais sont synchronisés
	@$(PY) tools/check_i18n.py

accept:		## enregistre TOUT l'état actuel comme référence (dangereux : masque les autres écarts)
	@$(PY) tools/check_i18n.py --accept

ignore:		## acquitte une divergence VOULUE pour une clé : make ignore k=section.cle[,autre]
	@test -n "$(k)" || { echo "usage : make ignore k=parcours.sii.bullet2[,autre.cle]"; exit 1; }
	@$(PY) tools/check_i18n.py --accept "$(k)"

pages:            ## contrôle avant publication GitHub Pages (chemins, HTTP, rendu)
	@$(PY) tools/check_pages.py

check: i18n build pages

serve:            ## aperçu local sur http://localhost:8000
	@$(PY) -m http.server 8000

clean:
	@rm -f content/.i18n-state.json
	@echo "référence de synchronisation effacée"
