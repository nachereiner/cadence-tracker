# F04 — Tableau de bord

- **Statut** : ✅ MVP
- **Code** : `ui/views/dashboard.py`, `ui/charts.py` (`metric_over_time`, `weekly_volume`), `analysis/stats.py`
- **Tests** : `tests/test_ui_smoke.py`, `tests/test_stats.py`

## Objectif

Voir d'un coup d'œil où en sont la cadence, l'allure et la FC, et comment elles évoluent, en distinguant une tendance d'une simple variation.

## Comportement

- **En-tête** (commun aux pages d'analyse), avec des choix conservés d'une page à l'autre :
  - le sélecteur **Route / Trail**. En mode Trail, on voit uniquement les sorties trail (terrain trail, ou classées trail), sans autre filtre ;
  - en mode Route, un seul filtre : **Type de séance** (endurance fondamentale, sortie longue, fractionné, seuil, autre). **Par défaut : endurance fondamentale et sortie longue**, les efforts comparables d'une semaine à l'autre ; les autres types s'ajoutent dans le menu.
- **Le chrono** (voir F11) :
  - la cadence médiane des 4 dernières semaines en grands chiffres ambrés, avec l'écart par rapport aux 4 précédentes ;
  - les 12 dernières semaines en barres ;
  - le couloir de progression vers l'objectif, ou une note si l'objectif ne peut pas encore être situé.

  À côté, trois tuiles : allure, FC, volume.
- **Évolution**, le graphique central sur deux étages partageant l'axe du temps. Il **remplace les anciens tableaux « Synthèse mensuelle » et « Volume hebdomadaire »**.
  - **Indicateur** : cadence (moyenne hors marche et arrêts), allure, FC, longueur de pas, FC à allure égale, efficacité brute.
  - **Regrouper par** : Jour, Semaine, Mois (par défaut) ou Année.
  - **Étage du haut** :
    - chaque sortie en point, coloré et formé selon sa famille de séance (toujours actif) ;
    - pour Semaine, Mois et Année, la valeur de la période en ligne craie. Son survol donne le détail de la période : sorties, km, durée, cadence, allure, FC, longueur de pas ;
    - pour Jour, la moyenne glissante sur 4 semaines ;
    - la tendance linéaire en pointillés et l'objectif de cadence.
  - **Étage du bas** : le volume en km par période, empilé par famille de séance.
  - **Période affichée** : un curseur de dates sous le graphique. Il cible une période précise et s'applique au graphique, à la tendance et au tableau des types. Le zoom Plotly reste disponible.
- **Phrase de tendance**, avec le même vocabulaire que les questions clés (« Stable » si l'effet est négligeable, effets par mois et par an), et à côté le petit tableau **Types de séance** (sorties, cadence médiane).
- *FC à allure égale* (`analysis/economy.py`) : la FC de chaque sortie continue est ramenée à l'allure de référence (allure médiane des EF sur route, arrondie à 5 s) et sur le plat. On utilise ses km (hors premier) et les pentes FC/vitesse et FC/pente estimées au sein des sorties. *Efficacité brute* (vitesse/FC) : elle dépend de l'allure et du terrain.

## Règles

- **Moyenne glissante** : moyenne sur 28 jours calendaires précédant chaque sortie, à partir de 3 sorties.
- **Agrégats par période** (`stats.aggregate_by_period`) : semaines du lundi au dimanche ; volume et durée en somme ; cadence, vitesse et FC pondérées par le temps de course (c'est la moyenne sur toutes les secondes courues de la période) ; longueur de pas = vitesse / cadence. Le chrono utilise la même moyenne pondérée sur 4 semaines.
- **Tendance** : régression linéaire sur la date, pente exprimée par mois de 30,44 jours. Elle est jugée en hausse ou en baisse si l'intervalle de confiance à 95 % exclut 0. Il faut au moins 6 sorties.
- **Allure** : l'axe est inversé (plus rapide en haut) et gradué en min/km.

### Règles visuelles

Elles valent pour tous les graphiques (`ui/charts.py`). L'identité complète est décrite dans [F11](F11-identite-visuelle.md).

- palette « Piste de nuit » validée pour les daltonismes ;
- au plus 3 couleurs catégorielles par nuage de points (familles : endurance, qualité, trail et autres) ;
- les périodes ordonnées utilisent un dégradé d'une seule teinte ;
- traits de 2 px, marqueurs d'au moins 8 px, grille fine continue, **jamais de double axe** ;
- les lignes de modèle (tendances) sont en pointillés ;
- chaque valeur est aussi lisible dans un tableau ou une infobulle.

## Critères d'acceptation

- [x] La page s'affiche sur les données de démo comme sur une base vide (message d'accueil), dans les deux modes et pour chaque regroupement. → `tests/test_ui_smoke.py`
- [x] Agrégats par mois et par semaine (pondération par le temps de course, volume par famille). → `tests/test_goal_and_periods.py`
- [x] Une pente simulée de +1,5 pas/min par mois est retrouvée. → `test_linear_trend_slope_per_month`

## Évolutions

- Charge d'entraînement (volume, TRIMP, ATL/CTL) en contexte.
- Annotations d'événements (changement de chaussures, blessure, début d'un plan).
