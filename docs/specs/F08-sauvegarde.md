# F08 — Sauvegarde (pas d'export)

- **Statut** : ✅ v0.2.1 (export supprimé)
- **Code** : `backup.py`, `cli.py` (`backup`), `ui/views/data.py`
- **Tests** : `tests/test_privacy.py`
- **Décision** : [ADR 0004](../adr/0004-aucune-donnee-gps.md)

## Objectif

Ne jamais perdre l'historique, sans jamais faire sortir les données de la machine.

## Comportement

- **Sauvegarde** : `ctrack backup` ou le bouton de Réglages › Import et synchronisation.
  - Elle prend un instantané cohérent de la base via l'API *online backup* de SQLite, ce qui reste sûr pendant que l'UI tourne.
  - Le fichier produit est `data/backups/cadence-AAAAMMJJ-HHMMSS.db`.
  - Les 10 dernières sauvegardes sont conservées.
  - Les sorties importées depuis la v0.2.1 n'ont aucune position GPS. Les positions plus anciennes restent au repos dans la base et ses sauvegardes, sans jamais être lues par l'application ; `ctrack purge-gps` les efface sur demande.
- **Aucun export** : ni commande, ni bouton. Les boutons de téléchargement intégrés à Streamlit et Plotly (CSV des tableaux, image des graphiques) sont masqués.
- **Restaurer** : copier une sauvegarde `.db` à la place de `data/cadence.db`, l'UI étant arrêtée.

## Critères d'acceptation

- [x] Une sauvegarde de données importées est lisible et ne contient aucune position. → `test_backup_of_new_data_contains_no_gps`
- [x] Aucun module ni aucune commande d'export n'existe. → `test_no_export_entry_point`
