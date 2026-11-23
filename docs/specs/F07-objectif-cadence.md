# F07 — Objectif de cadence

- **Statut** : ✅ v0.2 (simplifié : plus de « séances cadence »)
- **Code** : `analysis/cadence_goal.py`, `ui/views/goal.py`, `ui/charts.py` (`goal_projection`)
- **Tests** : `tests/test_demo_analyses.py::test_goal_status_and_classification`, `tests/test_goal_and_periods.py`

## Objectif

Savoir où l'on en est, à quel rythme on progresse, et quand on atteindra la cadence cible.

## Comportement

- **Formulaire** : cadence cible et date de début du travail de cadence.
- **Sorties prises en compte** :
  - en mode Route : le filtre « Type de séance » de la page, par défaut **endurance fondamentale et sortie longue** ;
  - en mode Trail : toutes les sorties trail.
- **Indicateurs** :
  - où vous en êtes : médiane des 4 dernières semaines ;
  - point de départ, et l'écart depuis ;
  - objectif, et le pourcentage du chemin parcouru ;
  - rythme, par mois et par an ;
  - **date estimée**, avec une fourchette.
- **Couloir de progression** du point de départ vers l'objectif.
- **Graphique** :
  - les sorties et leur moyenne glissante sur 4 semaines ;
  - la tendance depuis le début ;
  - une **projection** depuis le niveau actuel jusqu'à la date estimée, avec un **cône d'incertitude** (IC 95 % du rythme), la ligne d'objectif et un repère sur la date estimée.
- **Une phrase de synthèse** : « À votre rythme actuel (+x pas/min par mois), vous atteindrez … vers … ; la fourchette va de … à … ».

## Règles

- **Cadence ajustée** : `cadence moyenne (secondes de course) + b × (vitesse de référence − vitesse de la sortie)`.
  - `b` est la pente cadence/vitesse estimée au sein des sorties, sur les splits centrés par sortie. Elle est bornée entre 0 et 25, et vaut 8 à défaut de données.
  - La vitesse de référence est la vitesse médiane des sorties prises en compte.
- **Point de départ** : médiane de la cadence ajustée sur les 4 semaines avant le début du travail (ou les 4 suivantes, s'il y a moins de 3 sorties avant).
- **Rythme** : régression linéaire de la cadence ajustée, depuis le début du travail moins 4 semaines, et **au minimum sur les 12 dernières semaines**. Un objectif fixé il y a 3 semaines donnerait sinon une pente et une fourchette absurdes (constaté sur les données réelles).
- **Dates** :
  - date centrale = rythme estimé ;
  - au plus tôt = borne haute de l'IC ;
  - au plus tard = borne basse de l'IC.
  - Pas de date si le rythme est nul ou négatif, ou si l'échéance dépasse 3 ans.

## Critères d'acceptation

- [x] Sur la démo, `b` est estimé entre 4 et 14 (9 simulé), la cadence actuelle dépasse le point de départ, et les dates vérifient « au plus tôt ≤ centrale ≤ au plus tard ». → `test_goal_status_and_classification`
- [x] Calcul de l'échéance : +1 pas/min par mois pour 5 pas/min donne environ 5 mois ; un rythme nul ne donne pas de date ; au-delà de 3 ans, pas de date. → `test_eta`

## Évolutions

- Paliers intermédiaires, par exemple +3 pas/min toutes les 6 à 8 semaines.
