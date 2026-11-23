# Running Cadence Tracker — conventions de développement

Outil personnel et local : Python 3.12, uv, SQLite, Streamlit, Plotly. Lire d'abord `docs/architecture.md`, puis la spec de la fonctionnalité concernée dans `docs/specs/`.

## Commandes

- Tests : `uv run pytest` (environ 15 s ; `tests/test_ui_smoke.py` est le plus lent)
- Lint et format : `uv run ruff check src tests && uv run ruff format src tests`
- Démo : `uv run ctrack demo && uv run ctrack ui --demo`

## Règles

- **Spec d'abord** : une évolution fonctionnelle met à jour `docs/specs/FXX-*.md` (comportement, règles, critères d'acceptation) puis `docs/ROADMAP.md`. Chaque critère d'acceptation renvoie à un test.
- **Couches** : `ingest/`, `storage/` et `analysis/` n'importent jamais Streamlit. L'UI (`ui/`) ne contient pas de SQL : tout passe par `storage/repository.py`.
- **Modèle pivot** : toute nouvelle source produit un `models.ParsedActivity`, ou un fichier FIT passé à `pipeline.import_raw`.
- **Schéma** : on ne modifie jamais une migration déjà appliquée. On ajoute `storage/migrations/NNN_*.sql`.
- **Annotations utilisateur** (`session_type_manual`, `excluded`, `notes`, nom) : jamais écrasées par un import ou un recalcul.
- **Pages** : Tableau de bord, Corrélations, Objectif, Sorties, Comparer, Réglages. L'en-tête de chaque page (`common.page_header`) porte le mode Route/Trail et, en Route, le filtre Type de séance.
- **Algorithmes de métriques** : en cas de changement, incrémenter `analysis/metrics.METRICS_VERSION` et documenter dans F03.
- **Unités** : cadence en pas/min (les deux pieds), vitesse en m/s, allure en s/km (affichée en min/km), distances en m.
- **Statistiques** : un effet n'est jugé positif ou négatif que si son IC à 95 % exclut 0. Toujours rappeler qu'il s'agit d'associations.
- **Identité visuelle** (F11) : thème sombre « Piste de nuit » ; l'ambre `#FFB020` est réservé à « votre valeur actuelle ». Nouveaux composants de marque dans `ui/theme.py`, pas de CSS ailleurs.
- **Graphiques** (`ui/charts.py`, palette `NIGHT`) : couleurs validées pour les daltonismes, au plus 3 couleurs catégorielles par nuage de points, pas de double axe, tendances en pointillés, grands aplats en brume.
- **Langue** : interface et documentation en français ; identifiants et docstrings en anglais.

## Données et confidentialité

- **Jamais de GPS accessible** (ADR 0004) : aucune position ne sort des parsers ni n'est stockée par un nouvel import. Toute requête liste ses colonnes explicitement (jamais `SELECT *` sur `samples` ou `activity_metrics`). Pas d'export, pas de carte. `tests/test_privacy.py` le vérifie.

- Ne jamais committer `data/` (données personnelles) ni de clé API. La clé Garmin vit dans le Keychain (`keyring`).
- Ne pas envoyer de données d'activité vers un service tiers. Une nouvelle intégration externe doit être optionnelle, désactivée par défaut et documentée.
- L'API Strava n'est pas utilisée (ADR 0001) : sa politique limite le stockage à 7 jours et interdit l'usage de ses données avec une IA. Les fichiers de l'export Strava importés par l'utilisateur ne relèvent pas de cette API.
