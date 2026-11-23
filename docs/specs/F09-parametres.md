# F09 — Paramètres d'analyse

- **Statut** : ✅ MVP
- **Code** : `config.py` (`Settings`), `storage/repository.py` (`load_settings`/`save_settings`), `ui/views/settings_view.py`, affiché dans **Réglages › Paramètres généraux** (`ui/views/reglages.py`)
- **Tests** : `tests/test_pipeline.py::test_recompute_after_settings_change`

## Objectif

Adapter les seuils au coureur (FC max, cadence de marche, définition d'une sortie longue…) sans toucher au code.

## Paramètres

| Paramètre | Défaut | Effet |
|---|---|---|
| `hr_max` | estimée | base des seuils de FC de la classification |
| `min_run_speed_mps` | 1,8 m/s (6,5 km/h) | seuil course/marche, donc **recalcul des métriques** |
| `min_run_cadence_spm` | 130 | idem |
| `ef_max_hr_pct` | 80 % | classification EF |
| `tempo_min_hr_pct` | 86 % | classification seuil |
| `long_run_min_duration_min` / `long_run_min_distance_km` | 80 min / 16 km | sortie longue |
| `trail_min_ascent_m_per_km` | 25 | trail |
| `interval_min_speed_cv` | 0,10 | fractionné : variabilité d'allure hors arrêts |
| `interval_min_fast_blocks` | 4 | fractionné : nombre d'efforts tenus 30 s |
| `cadence_target_spm`, `cadence_goal_start` | — | objectif cadence (F07) |
| `natural_session_types` | EF, sortie longue | types de séance proposés par défaut sur la page Objectif |
| `garmin_history_start` | — | borne de la synchro complète |

## Règles

- Les paramètres sont stockés en JSON dans la table `settings`. Les clés inconnues sont ignorées et les nouvelles clés prennent leur valeur par défaut, ce qui garantit la compatibilité ascendante.
- Si un seuil course/marche change, on lance un **recalcul complet** (`recompute_all`) ; sinon, une **reclassification** suffit.
- Chemins : `CTRACK_DATA_DIR` (dossier de données, `./data` par défaut) et `CTRACK_DB` (base utilisée, que `--demo` fixe sur `data/demo.db`).

## Critères d'acceptation

- [x] Abaisser la vitesse minimale de course puis recalculer fait passer un footing lent de « marche » à « course ». → `test_recompute_after_settings_change`
