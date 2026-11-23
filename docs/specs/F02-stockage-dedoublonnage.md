# F02 — Stockage, dédoublonnage, idempotence

- **Statut** : ✅ MVP
- **Code** : `storage/db.py`, `storage/migrations/`, `storage/repository.py`, `ingest/pipeline.py`
- **Tests** : `tests/test_pipeline.py`

## Objectif

Pouvoir relancer n'importe quel import ou synchro sans créer de doublon, et sans jamais perdre ni les corrections de l'utilisateur ni les données d'origine.

## Règles

### Dédoublonnage, dans l'ordre

1. **Même contenu de fichier** (SHA-256 du fichier décompressé, table `seen_files`) déjà vu : `already_imported`, sans même parser.
2. **Même identifiant source** (`source`, `source_id`), par exemple le même `activityId` Garmin : `duplicate`.
3. **Même sortie venue d'une autre source**, c'est-à-dire un départ à ±2 min et une durée proche (écart ≤ 15 % + 60 s) :
   - on compare la **richesse** des deux versions, dans cet ordre : présence de la cadence, de la FC, puis nombre de points ;
   - si la nouvelle version est plus riche, elle **remplace les données** (séries, tours, splits, métriques) de l'activité existante : `updated` ;
   - sinon, elle est ignorée : `duplicate`.

### Ce qui n'est jamais écrasé

Le type de séance manuel, l'exclusion, les notes et le nom donné par l'utilisateur.

### Pas d'archive des fichiers originaux

Les fichiers importés ne sont **pas conservés**, car ils contiennent la trace GPS (ADR 0004). Seule leur empreinte SHA-256 est gardée, pour le dédoublonnage.

### Migrations

Ce sont des fichiers SQL numérotés (`001_initial.sql`, `002_…`), appliqués au démarrage. Le niveau atteint est stocké dans `PRAGMA user_version`. **Un fichier déjà appliqué n'est jamais modifié** : toute évolution passe par un nouveau fichier.

### Concurrence

SQLite tourne en mode WAL, ce qui permet à l'UI de lire pendant qu'une synchro en ligne de commande écrit.

## Critères d'acceptation

- [x] Réimporter le même fichier ne crée rien. → `test_import_then_reimport_is_idempotent`
- [x] Le GPX d'une sortie déjà importée en FIT est un doublon. → `test_same_run_from_another_source_is_a_duplicate`
- [x] Une version plus riche remplace les données et conserve les annotations. → `test_richer_version_replaces_data_but_keeps_annotations`
- [x] Un même identifiant Garmin n'est jamais importé deux fois. → `test_same_source_id_is_not_imported_twice`

## Évolutions

- Fusion multi-sources : par exemple garder le GPS d'une source et la cadence d'une autre.
