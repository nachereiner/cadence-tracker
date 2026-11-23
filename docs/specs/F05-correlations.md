# F05 — Analyse des corrélations et questions clés

- **Statut** : ✅ MVP
- **Code** : `analysis/stats.py`, `analysis/questions.py`, `ui/views/correlations.py`, `ui/charts.py` (`scatter_by_period`, `explorer_scatter`)
- **Tests** : `tests/test_stats.py`, `tests/test_demo_analyses.py`, `tests/test_charts.py`
- **Décision** : [ADR 0003](../adr/0003-analyses-ajustees.md)

## Objectif

Répondre, chiffres à l'appui et **sans confondre corrélation et causalité**, aux questions du projet. La difficulté centrale est de neutraliser les facteurs de confusion : allure, pente, type de séance, durée et terrain.

## Comportement

### Questions clés

Chaque question s'affiche dans une carte qui contient :

- une **réponse en une phrase**, avec l'ampleur de l'effet et son intervalle de confiance à 95 % ;
- un badge : *Progrès*, *À surveiller*, *Stable* ou *Données insuffisantes* ;
- un graphique ;
- une section « Méthode et limites » : formule du modèle, R², p, coefficients.

| # | Question | Méthode | Données | Contrôles |
|---|---|---|---|---|
| 1 | Ma cadence augmente-t-elle au fil des semaines ? | tendance linéaire de la cadence médiane (effet **brut**) | sorties filtrées | — |
| 2 | À allure équivalente, ma cadence augmente-t-elle ? | OLS `cadence ~ temps + vitesse + pente + C(type)` | km, hors tapis | vitesse, pente, type |
| 3 | À cadence équivalente, mon allure s'améliore-t-elle ? | OLS `allure (s/km) ~ temps + cadence + pente + C(type)` | km, hors tapis | cadence, pente, type |
| 4 | À allure et conditions comparables, ma FC diminue-t-elle ? | OLS `FC ~ temps + vitesse + pente + temps écoulé + C(type)` | km de séances continues (EF, SL, seuil), hors tapis | vitesse, pente, dérive cardiaque, type |
| 5 | Ma cadence reste-t-elle stable pendant une sortie longue ? | moyenne (et IC) des pentes de cadence au sein des sorties | sorties longues ou ≥ 1 h | — (effet brut) |
| 6 | Ma cadence diminue-t-elle avec la fatigue ? | moyenne (et IC) des pentes cadence ~ temps + vitesse | séances continues ≥ 40 min | vitesse |

- Pour les questions 2 à 4, le graphique est un nuage de km coloré par **période** (3 périodes : bleu, rose, puis ambre pour la plus récente), avec une droite par période. Des droites qui montent d'une période à l'autre signifient une hausse à x égal.
- À la question 3, un rappel s'affiche : si la cadence augmente à allure égale, il est **attendu** qu'à cadence égale l'allure soit plus lente (foulée plus courte), et ce n'est pas une baisse de forme.

### Période et filtres

L'en-tête Route/Trail et Type de séance s'applique, ainsi qu'un curseur **Période analysée**, partagé avec le tableau de bord. L'ancien onglet Explorateur a été retiré pour simplifier l'application (v0.2).

## Règles

- Les km d'une même sortie ne sont pas indépendants : erreurs standard **groupées par sortie**, à partir de 10 sorties.
- Un effet n'est jugé positif ou négatif que si son IC à 95 % exclut 0 ; sinon la réponse est « pas d'évolution nette ».
- **Effet négligeable** : sur un long historique, un effet minuscule devient statistiquement significatif. Si tout l'IC reste sous un seuil d'intérêt pratique, la réponse est « Stable : l'évolution est mesurable mais négligeable ». Seuils par mois : cadence 0,1 pas/min (1,2 par an), allure 1 s/km, FC 0,1 bpm.
- Les effets sont affichés par mois **et par an**, avec 2 décimales quand ils sont petits.
- Seuils minimaux : 15 km pour un modèle, 6 sorties pour une tendance, 3 sorties pour une moyenne de pentes.
- Les filtres s'appliquent. Pour étudier la progression technique pure, on se place en mode Route et on filtre sur **Endurance fondamentale**.
- Chaque page rappelle qu'**une association n'est pas une causalité**.

## Critères d'acceptation

- [x] Si la cadence ne dépend que de la vitesse et que la vitesse augmente avec le temps, l'effet brut du temps est positif mais l'effet ajusté est nul. → `test_adjusted_effect_removes_confounding_by_pace`
- [x] Sur la démo (effets simulés connus) : cadence en hausse à allure égale, FC à allure égale en baisse avec un IC compatible avec −0,8 bpm/mois, baisse de cadence avec la fatigue. → `test_questions_recover_simulated_effects`
- [x] Les nuages par période comptent au plus 3 périodes, en bleu, rose puis ambre ; la plus récente est toujours en ambre et chaque droite prend la couleur de sa période. → `test_periods_use_three_distinct_hues_latest_amber`, `test_fewer_periods_keep_the_latest_in_amber`

## Limites connues / évolutions

- La météo n'est pas prise en compte ; la température du capteur de la montre n'est pas fiable. Évolution : une API météo historique, à activer explicitement puisque c'est un service tiers.
- Modèles à effets mixtes et effets non linéaires du temps (splines).
- Comparaison avant/après un événement (début du travail de cadence), en *interrupted time series*.
