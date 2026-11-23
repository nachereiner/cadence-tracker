# Feuille de route

Ce fichier sert au suivi de projet. Chaque ligne renvoie à une spec (`docs/specs/`) ; une case cochée signifie « livré et testé ».

## v0.1 — MVP (19/11/2026) ✅

- [x] Étude des sources de données ([rapport](research/sources-de-donnees.md), [ADR 0001](adr/0001-sources-de-donnees.md))
- [x] Import FIT, TCX, GPX, ZIP imbriqués et gzip ; export complet Garmin et Strava — F01
- [x] Synchro Garmin via l'API personnelle officielle : incrémentale, reprises, clé dans le Keychain — F01
- [x] Stockage SQLite, archive des fichiers bruts, dédoublonnage multi-source, idempotence — F02
- [x] Cadence normalisée en pas/min, détection course/marche, métriques et splits au km — F03
- [x] Tableau de bord : indicateurs sur 4 semaines, évolution, moyenne glissante, tendance, filtres — F04
- [x] Six questions clés en régression ajustée, plus un explorateur de corrélations — F05
- [x] Classification automatique et corrections manuelles — F06
- [x] Objectif cadence : cadence naturelle ajustée, progression, transfert, suggestions — F07
- [x] Sauvegarde et export complet — F08
- [x] Paramètres d'analyse avec recalcul — F09
- [x] Détail d'une sortie (séries synchronisées, zoom) et comparaison de deux sorties — F10
- [x] Base de démonstration synthétique et suite de tests (parsers, pipeline, stats, synchro simulée, UI headless)

## v0.1.1 — Identité visuelle (19/11/2026) ✅

- [x] Thème sombre « Piste de nuit », logo original, typographie DIN — F11
- [x] Navigation en haut et ligne de filtres conservée d'une page à l'autre — F04/F11
- [x] Chrono de cadence, bande hebdomadaire et couloir de progression sur le tableau de bord — F04
- [x] Tuiles de statistiques responsives (Détail, Objectif, Données) ; affichage vérifié à 390 px — F11

## v0.1.2 — Calage sur données réelles (19/11/2026) ✅

- [x] Première synchro Garmin : 616 activités listées, 443 courses importées (FR255, depuis 2023), sans erreur — F01
- [x] La catégorie Garmin fait foi sur le type du fichier ; les activités ignorées sont journalisées — F01
- [x] Détection du fractionné hors arrêts (`speed_cv`, `fast_blocks`) ; mots-clés du plan d'entraînement (Allure 21, Seuil, Base…) — F03/F06
- [x] Tapis sans vitesse : détection de la course par la cadence — F03
- [x] Cadence naturelle limitée à la route et à la piste — F07
- [x] Effets négligeables présentés comme stables ; effets aussi exprimés par an — F05
- [x] Indicateur « FC à allure égale » (ajusté à l'allure et à la pente) : l'efficacité brute masquait le progrès — F04

## v0.2 — Simplification (19/11/2026) ✅

- [x] Sélecteur Route / Trail ; un seul filtre, Type de séance, en mode Route — F04
- [x] Graphique central « Évolution » : Jour / Semaine / Mois / Année, volume empilé par type, curseur de période. Il remplace la synthèse mensuelle et le volume hebdomadaire — F04
- [x] Couleur par type de séance toujours active ; suppression de la notion de « séance cadence » — F04/F07
- [x] Objectif : progression, rythme, projection avec fourchette, date estimée — F07
- [x] Corrélations sans l'Explorateur ; page Détail retirée ; Comparer jusqu'à 5 sorties — F05/F10
- [x] Sorties : bouton « Synchroniser mes nouvelles sorties », liste repliée ; « Réglages » avec deux onglets — F01/F06/F09
- [x] Cadence de référence = moyenne pondérée par le temps de course : la médiane des pas entiers figeait les agrégats — F03/F04

## v0.2.1 — Zéro GPS, zéro export (19/11/2026) ✅

- [x] Positions GPS jamais lues (FIT) ou oubliées après calcul de distance (GPX/TCX) ; requêtes limitées aux colonnes autorisées : l'app ne charge jamais de GPS — ADR 0004
- [x] Fichiers originaux non conservés ; export supprimé (CLI, UI, boutons de téléchargement) — F08
- [x] Données GPS existantes laissées au repos (choix de l'utilisateur) ; `ctrack purge-gps` pour les effacer sur demande

## v0.3 — Suite

- [x] Clé Garmin créée, synchro complète validée : réponses conformes, historique accessible jusqu'en 2023, FIT complets — F01
- [ ] Calibrer FC max et seuils de classification sur les vraies séances, puis corriger quelques classifications — F06/F09
- [x] Objectif cadence défini (175 pas/min) — F07
- [ ] Synchro planifiée chaque matin (`launchd`) et sauvegarde automatique — F01/F08
- [ ] Alerte d'expiration de la clé Garmin (date `exp` du jeton) — F01

## Backlog (à prioriser)

- [ ] Allure ajustée à la pente (GAP) comme variable de contrôle — F03/F05
- [ ] Dynamiques de course FIT (temps de contact, oscillation verticale, longueur de foulée mesurée) — F03
- [ ] Météo (température, vent) via une API historique, en option et clairement signalée comme service tiers — F05
- [ ] Charge d'entraînement (ATL/CTL/TSB) en contexte des tendances — F04
- [ ] Modèles à effets mixtes, effet du temps non linéaire — F05
- [ ] Zones de FC personnalisées (LT1/LT2) — F06

## Journal des décisions

| Date | Décision | Référence |
|---|---|---|
| 19/11/2026 | API personnelle Garmin + fichiers ; pas d'API Strava (stockage limité à 7 jours) | ADR 0001 |
| 19/11/2026 | Python, SQLite, Streamlit + Plotly | ADR 0002 |
| 19/11/2026 | Progression mesurée par régression ajustée (km, erreurs groupées par sortie) | ADR 0003 |
| 19/11/2026 | Identité « Piste de nuit » : un seul accent ambre, DIN, navigation en haut | F11 |
| 19/11/2026 | Simplification : mode Route/Trail, graphique central, retrait du Détail, de l'Explorateur et des séances cadence | F04, F07, F10 |
| 19/11/2026 | Aucune donnée GPS, aucun export, fichiers originaux non conservés | ADR 0004 |
| 23/11/2026 | Installation locale par utilisateur, sans accès réseau ni mobile (option `--lan` retirée) | architecture |
