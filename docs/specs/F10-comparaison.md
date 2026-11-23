# F10 — Comparaison de sorties

- **Statut** : ✅ v0.2 (la page Détail a été retirée)
- **Code** : `ui/views/compare.py`, `ui/charts.py` (`compare_overlay`)
- **Tests** : `tests/test_ui_smoke.py::test_compare_three_runs`

## Objectif

Superposer plusieurs sorties, typiquement le même parcours à quelques semaines d'écart, pour voir comment la cadence, l'allure et la FC évoluent au même kilomètre.

## Comportement

- **Sorties à comparer** : on en choisit **de 2 à 5** dans une liste qui respecte le mode Route/Trail. La première sert de référence.
  - Par défaut, la page propose la dernière sortie et la plus similaire : distance à ±15 %, départ à moins de 500 m, même type de séance de préférence.
  - Une légende cite d'autres sorties similaires que l'on peut ajouter.
- **Graphique** : trois panneaux sur un axe en distance (cadence, allure, FC), avec un survol unifié et un lissage réglable de 5 à 120 s.
  - Les couleurs sont dans l'ordre ambre, bleu, rose, violet, vert, une palette validée pour les daltonismes en paires adjacentes sur fond sombre.
- **Tableau** : une ligne par sortie (distance, durée, allure, cadence, FC, longueur de pas, D+).

## Évolutions

- (L'alignement par segment GPS est exclu : l'application ne conserve aucune donnée GPS, voir ADR 0004.)
