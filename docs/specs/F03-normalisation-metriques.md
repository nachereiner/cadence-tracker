# F03 — Normalisation des séries et métriques par sortie

- **Statut** : ✅ MVP
- **Code** : `units.py` (`cadence_to_spm`), `ingest/pipeline.py` (`clean_samples`), `analysis/metrics.py`
- **Tests** : `tests/test_metrics.py`, `tests/test_parsers.py::test_cadence_unit_normalisation`

## Objectif

Des métriques comparables d'une sortie à l'autre, quelle que soit la source, et qui ne mesurent **que la course**, sans la marche ni les arrêts.

## Règles

### Aucune position GPS

Les séries ne contiennent ni latitude ni longitude (ADR 0004). La distance vient de la montre ; pour un GPX qui n'en a pas, elle est calculée à partir des coordonnées, en mémoire, dans le parser.

### Cadence

- Elle est toujours stockée en **pas par minute** (les deux pieds).
- Le FIT (et les exports TCX/GPX de Garmin) l'enregistrent en **foulées/min** (un pied, environ 80 à 95) : on additionne `cadence` et `fractional_cadence`, puis on multiplie par 2.
- Contrôle de cohérence : une unité déclarée « foulées » dont la médiane dépasse 130 est déjà en pas, et n'est pas doublée.
- Unité inconnue : on double si la médiane des valeurs positives est inférieure à 120.
- Les valeurs ≤ 0 ou > 260 sont supprimées.

### Nettoyage

- FC ≤ 0 : supprimée.
- Vitesse > 12 m/s : supprimée (aberration du capteur).

### Rééchantillonnage à 1 Hz

- Les trous de 10 s au plus sont comblés par le dernier point connu, et la distance par interpolation.
- Au-delà de 10 s, c'est une **pause** (montre arrêtée).
- La vitesse vient du capteur ; à défaut, on la dérive de la distance.
- Vitesse lissée : moyenne glissante centrée sur 9 s.

### Masques

- **Vitesse inexploitable** (tapis sans capteur : vitesse ≈ 0 alors que la montre mesure une cadence de course) : on ignore la vitesse et on détecte la course à partir de la cadence seule. L'allure reste alors vide.

- **En mouvement** : vitesse lissée ≥ 0,8 m/s, hors pause.
- **En course** : en mouvement, avec une vitesse ≥ `min_run_speed_mps` (6,5 km/h par défaut) et une cadence ≥ `min_run_cadence_spm` (130 par défaut).

### Métriques (table `activity_metrics`)

| Métrique | Définition |
|---|---|
| `cadence_mean/median/p10/p90/std` | secondes « en course » avec cadence. **La référence dans toute l'application est `cadence_mean`** : la montre enregistre des pas entiers, donc la médiane d'une sortie est toujours un nombre entier, trop grossier pour suivre une progression. Une médiane de médianes restait bloquée à 165,0 pour 2023, 2024 et 2025 sur les données réelles. |
| `avg_speed_mps` (et l'allure qui en découle) | moyenne de la vitesse en course |
| `hr_mean` | secondes en mouvement ; `hr_peak` = maximum de la FC moyennée sur 30 s |
| `ascent_m`, `descent_m` | valeurs de la montre si disponibles, sinon altitude lissée sur 15 s avec une hystérésis de 2 m |
| `ascent_per_km` | D+ / distance |
| `stride_m` (longueur de pas) | vitesse / (cadence / 60) |
| `efficiency` | vitesse (m/min) / FC : plus c'est haut, plus la course est économique |
| `decoupling_pct` | baisse de l'efficacité entre la 1re et la 2e moitié (≥ 20 min) |
| `cadence_first_half`, `cadence_second_half` | médianes des deux moitiés |
| `cadence_drift_spm_h` | pente de la cadence par minute en fonction du temps, hors 5 premières minutes, sur 15 minutes au moins |
| `cadence_fatigue_spm_h` | même pente **à vitesse constante** : régression cadence ~ temps + vitesse |
| `speed_cv` | coefficient de variation de la vitesse moyennée sur 30 s, **sur les seules secondes de course** : les arrêts (feux, pauses) sont exclus |
| `fast_blocks` | nombre d'efforts **tenus au moins 30 s** à une vitesse (moyennée sur 20 s) supérieure d'au moins 15 % à la médiane de la sortie. Signature des répétitions ; le bruit GPS et les lignes droites courtes ne comptent pas |
| `n_active_laps`, `n_rest_laps`, `active_lap_mean_s` | tours de la montre selon leur intensité |

### Splits au kilomètre (table `splits`)

Pour chaque km (le dernier aussi s'il fait au moins 200 m) : distance, durée en mouvement, vitesse, cadence en course, FC, D+, pente moyenne et temps écoulé en fin de km.

### Version

`METRICS_VERSION` est stockée avec chaque ligne (version 2 : `speed_cv` hors arrêts, `fast_blocks`, repli sur la cadence). Après un changement d'algorithme, on l'incrémente puis on lance `ctrack recompute`.

## Critères d'acceptation

- [x] Une sortie régulière à 3 m/s et 170 pas/min donne exactement ces valeurs, la bonne longueur de pas et 11 splits pour 10,8 km. → `test_steady_run_metrics`
- [x] 5 minutes de marche à 110 pas/min n'abaissent pas la cadence moyenne. → `test_walk_breaks_are_excluded_from_cadence`
- [x] Une baisse simulée de 3 pas/min par heure à allure constante est retrouvée malgré une allure variable. → `test_cadence_fatigue_is_measured_at_constant_pace`

## Évolutions

- Allure ajustée à la pente (GAP), grâce à un modèle de coût énergétique.
- Dynamiques de course du FIT (temps de contact au sol, oscillation verticale, longueur de foulée mesurée), utiles pour l'analyse technique.
