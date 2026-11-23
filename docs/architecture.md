# Architecture

## Principes

1. **Local d'abord, sans GPS accessible** : une base SQLite sur la machine. L'application ne lit, n'affiche ni n'exporte aucune position GPS (ADR 0004). Aucun service tiers, sauf l'API Garmin officielle pour la synchro, et un fond de carte optionnel désactivé par défaut.
2. **Normalisé → calculé** : les fichiers sont parsés puis oubliés ; on garde des séries normalisées, sans position, et des métriques recalculables. Une amélioration d'algorithme se rejoue sur tout l'historique (`ctrack recompute`).
3. **Le cœur ne dépend pas de l'interface** : `ingest`, `storage` et `analysis` ne connaissent pas Streamlit. On pourrait remplacer l'UI (par exemple par FastAPI et une SPA) sans toucher au reste.
4. **Idempotence** : relancer un import ou une synchro ne crée jamais de doublon et n'écrase jamais une annotation de l'utilisateur.
5. **Simplicité** : un seul langage (Python), un seul fichier de base, aucun serveur à administrer.

## Vue d'ensemble

```
             ┌──────────────────────────┐      ┌───────────────────────────────┐
             │  Garmin Personal API     │      │ Fichiers FIT / TCX / GPX / ZIP│
             │  (clé dans le Keychain)  │      │ (export Garmin, Strava, USB)  │
             └────────────┬─────────────┘      └──────────────┬────────────────┘
                          │ ZIP (FIT original)                │
                          ▼                                   ▼
                  ingest/garmin.py                     ingest/files.py
                          └───────────────┬───────────────────┘
                                          ▼
                     parsers : ingest/fit.py · ingest/xml_formats.py
                                          │  ParsedActivity (models.py) = modèle pivot
                                          ▼
                                  ingest/pipeline.py
              nettoyage · cadence en pas/min · dédoublonnage · archivage brut
                                          │
                  ┌───────────────────────┼─────────────────────────┐
                  ▼                       ▼                         ▼
          data/raw/<fmt>/…        analysis/metrics.py      analysis/classification.py
          (fichiers originaux)    métriques + splits km     type de séance auto
                                          │
                                          ▼
                             storage (SQLite, data/cadence.db)
                                          │
                       analysis/stats.py · questions.py · cadence_goal.py
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
           ui/ (Streamlit + Plotly)                       cli.py (Typer)
```

## Modules

| Module | Rôle | Spec |
|---|---|---|
| `models.py` | `ParsedActivity`, le **modèle pivot** produit par chaque source | F01 |
| `ingest/files.py` | découverte des fichiers, ZIP imbriqués, gzip, détection du format | F01 |
| `ingest/fit.py`, `ingest/xml_formats.py` | parsers FIT, TCX et GPX | F01 |
| `ingest/garmin.py` | synchro via l'API personnelle Garmin (incrémentale, reprises) | F01 |
| `ingest/pipeline.py` | nettoyage, dédoublonnage, archivage, recalcul | F02 |
| `storage/db.py`, `storage/migrations/*.sql` | connexion SQLite (WAL) et migrations numérotées | F02 |
| `storage/repository.py` | **tout le SQL** ; renvoie des DataFrames | F02 |
| `analysis/metrics.py` | rééchantillonnage à 1 Hz, détection course/marche, métriques, splits, dérive | F03 |
| `analysis/classification.py` | règles de type de séance | F06 |
| `analysis/stats.py` | tendances, régressions ajustées, agrégats par période | F04, F05 |
| `analysis/economy.py` | FC ramenée à une allure de référence sur le plat | F04 |
| `analysis/questions.py` | les 6 questions clés, réponses en français | F05 |
| `analysis/cadence_goal.py` | cadence ajustée, rythme, projection et date estimée | F07 |
| `backup.py` | sauvegarde SQLite locale (pas d'export) | F08 |
| `config.py` | chemins et paramètres d'analyse | F09 |
| `ui/` | pages Streamlit (`views/` : tableau de bord, corrélations, objectif, sorties, comparer, réglages), graphiques (`charts.py`), en-tête Route/Trail et données (`common.py`), identité visuelle (`theme.py`, `assets/`) | F04–F11 |
| `demo.py` | historique synthétique (démo et tests de bout en bout) | — |

## Modèle de données (SQLite)

Fichier : `data/cadence.db` (ou `$CTRACK_DB`). Les migrations vivent dans `storage/migrations/NNN_*.sql`, et le niveau appliqué est stocké dans `PRAGMA user_version`.

| Table | Contenu | Recalculable ? |
|---|---|---|
| `activities` | identité (source, id source, début UTC, décalage horaire), terrain, **annotations utilisateur** (type manuel, exclusion, notes). La colonne `cadence_focus` héritée de la v0.1 n'est plus utilisée | non : c'est la vérité utilisateur |
| `samples` | séries temporelles (t, distance, vitesse, cadence en pas/min, FC, altitude). Les anciennes colonnes `lat`/`lon` d'une base antérieure restent au repos, **jamais lues** ; elles sont vides pour les nouveaux imports | non (fichiers non conservés) |
| `laps` | tours de la montre (durée, distance, intensité) | oui |
| `splits` | découpage au km (allure, cadence, FC, pente) | oui, depuis `samples` |
| `activity_metrics` | métriques agrégées et classification auto (`metrics_version`) | oui, depuis `samples` |
| `seen_files` | empreintes des fichiers déjà importés (SHA-256, nom, source), pour le dédoublonnage | — |
| `import_log`, `sync_state` | journal des imports, curseur de synchro | — |
| `settings` | paramètres d'analyse (JSON) | — |

Le **type effectif** d'une séance vaut `COALESCE(activities.session_type_manual, activity_metrics.session_type_auto)`.

## Flux

- **Import de fichier** : `iter_raw_files` → `import_raw` → si le SHA-256 est connu, on s'arrête (`already_imported`) ; sinon on parse, on archive dans `raw/` puis on appelle `ingest_parsed` (dédoublonnage, stockage, métriques). En fin de lot, `reclassify`.
- **Synchro Garmin** : `search_activities`, paginé depuis la dernière activité moins 3 jours. Pour chaque course dont l'identifiant n'a jamais été vu : `download_activity` (ZIP) → `import_raw(source="garmin_api")`. Le curseur n'avance que si la synchro va au bout.
- **Changement de paramètres** : `recompute_all` recalcule les métriques et les splits depuis `samples`, puis relance la classification.

## Sécurité et confidentialité

- La clé Garmin est rangée dans le **trousseau du système** (`keyring`, Keychain sur macOS), jamais dans le dépôt. Le jeton bearer est mis en cache dans `~/.config/cadence-tracker/` en `0600`.
- `data/` est exclu de git (`.gitignore`).
- **Aucune donnée GPS** n'est lue, affichée ni exportable par l'application : les colonnes sont listées explicitement dans chaque requête (`privacy.py`). Les nouveaux imports n'en stockent pas ; `ctrack purge-gps` efface les anciennes sur demande (ADR 0004).
- L'UI écoute uniquement sur `127.0.0.1` : elle n'a pas d'authentification et n'est jamais accessible depuis le réseau. Chaque utilisateur installe l'application sur son propre poste.
- La télémétrie Streamlit est désactivée (`.streamlit/config.toml`).

## Choix techniques

Les choix sont justifiés dans les ADR : [`docs/adr/`](adr/).
