# Running Cadence Tracker

Un outil **personnel et local** pour suivre l'évolution de sa **cadence de course** et comprendre ses liens avec l'**allure** et la **fréquence cardiaque**.

Il répond à quelques questions concrètes : la cadence augmente-t-elle vraiment, **à allure égale** ? La FC baisse-t-elle à allure et conditions comparables ? La cadence travaillée devient-elle naturelle ?

- Données récupérées automatiquement depuis **Garmin Connect** (API personnelle officielle), ou importées depuis des fichiers **FIT, TCX, GPX ou ZIP** (exports complets Garmin et Strava compris).
- Tout reste sur la machine : une base SQLite dans `data/`. Aucune donnée GPS n'est accessible depuis l'application, aucun export. Pas de cloud, pas de télémétrie.
- Interface web locale au thème sombre « Piste de nuit » : tableau de bord (mode Route ou Trail), corrélations, objectif cadence avec date estimée, sorties, comparaison de sorties, réglages.

## Installation

Chacun installe l'application sur son propre ordinateur. Elle n'est accessible que depuis ce poste.

1. Installer [uv](https://docs.astral.sh/uv/getting-started/installation/) (il installe lui-même Python si besoin).
2. Récupérer le projet et installer les dépendances :

   ```bash
   git clone https://github.com/nachereiner/cadence-tracker.git
   cd cadence-tracker
   uv sync
   ```

3. Lancer l'interface, puis ouvrir http://127.0.0.1:8501 :

   ```bash
   uv run ctrack ui
   ```

Pour essayer sans vos données : `uv run ctrack demo` puis `uv run ctrack ui --demo`.

## Importer vos sorties

- **Garmin** : créer une clé sur https://connect.garmin.com/app/settings/personalApiToken, puis dans l'interface **Réglages › Import et synchronisation**. Ensuite, le bouton **« Synchroniser mes nouvelles sorties »** de la page Sorties récupère les nouvelles activités.
- **Fichiers** : export complet Garmin ou Strava, fichiers FIT, TCX ou GPX, depuis **Réglages › Import et synchronisation**.

La même chose en ligne de commande :

```bash
uv run ctrack garmin set-key        # clé stockée dans le trousseau du système
uv run ctrack garmin sync --full    # premier import de tout l'historique
uv run ctrack import ~/Downloads/export-garmin.zip
```

Mettre à jour l'application : `git pull && uv sync`.

## Commandes

| Commande | Rôle |
|---|---|
| `ctrack ui [--demo] [--port N]` | lance l'interface sur http://127.0.0.1:8501 |
| `ctrack import CHEMIN…` | importe des fichiers, dossiers ou archives |
| `ctrack garmin set-key / status / sync [--since D] [--full] / forget-key` | synchronisation Garmin |
| `ctrack recompute` | recalcule métriques et classification (après un changement d'algorithme) |
| `ctrack backup` | sauvegarde locale de la base (`data/backups/`, 10 dernières conservées) |
| `ctrack purge-gps` | *optionnel, irréversible* : efface du disque les positions GPS héritées des versions antérieures (base, sauvegardes, fichiers originaux) |
| `ctrack demo` | (re)crée la base de démonstration `data/demo.db` |

Ajouter `--demo` à une commande la fait agir sur la base de démonstration.

## Confidentialité

- La clé Garmin est rangée dans le trousseau du système. Le jeton temporaire est stocké dans `~/.config/cadence-tracker/`, avec des droits restreints à l'utilisateur.
- **Aucune donnée GPS** n'est lue, affichée ni exportable par l'application, qui n'a **aucune fonction d'export** (ADR 0004). Les nouveaux imports ne stockent ni positions ni fichiers originaux.
- `data/` (base et sauvegardes) est exclu de git.
- L'interface n'écoute que sur `127.0.0.1` : elle n'est jamais accessible depuis le réseau.
- Aucun appel externe hors synchro Garmin.

## Documentation

| Document | Contenu |
|---|---|
| [docs/research/sources-de-donnees.md](docs/research/sources-de-donnees.md) | étude Garmin, Strava et fichiers : accès, limites, conditions |
| [docs/architecture.md](docs/architecture.md) | architecture, modules, modèle de données, flux, sécurité |
| [docs/adr/](docs/adr/) | décisions d'architecture |
| [docs/specs/](docs/specs/) | **une spec par fonctionnalité** (comportement, règles, critères d'acceptation reliés aux tests) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | suivi de projet : livré, prochaine étape, backlog |

## Développement

```bash
uv run pytest            # tests (parsers, pipeline, stats, synchro simulée, UI headless)
uv run ruff check src tests && uv run ruff format src tests
```

Conventions : [CLAUDE.md](CLAUDE.md). Le cœur (`ingest/`, `storage/`, `analysis/`) ne dépend pas de l'UI. Tout le SQL se trouve dans `storage/repository.py`. Toute évolution de schéma passe par une nouvelle migration `storage/migrations/NNN_*.sql`.
