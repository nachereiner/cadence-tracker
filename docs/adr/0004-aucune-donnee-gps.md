# ADR 0004 — Aucune donnée GPS accessible, aucun export

- **Statut** : accepté (19/11/2026)

## Contexte

L'application suit la cadence et les métriques de course. La position GPS ne sert à aucune de ses analyses : la distance est fournie par la montre, et l'altitude suffit pour la pente. Or la trace GPS est la donnée la plus sensible d'une sortie, puisqu'elle révèle le domicile, les horaires et les trajets habituels.

Exigence : une personne qui accède à l'application (interface ou serveur) ne doit **jamais pouvoir consulter ni exporter** de données GPS. L'effacement des données déjà présentes n'est pas exigé.

## Décision

1. **Aucune lecture par l'application** (`privacy.py`, `storage/repository.py`) :
   - toutes les requêtes listent explicitement leurs colonnes (`ALLOWED_SAMPLE_COLUMNS`, `METRIC_COLUMNS`) ;
   - les colonnes GPS d'une ancienne base ne sont **jamais chargées** en mémoire, ni envoyées au navigateur.
2. **Rien de nouveau n'est stocké** :
   - le parser FIT **ne lit pas** les champs de position ;
   - les parsers TCX et GPX lisent les coordonnées **uniquement en mémoire**, pour calculer une distance absente, puis les oublient ;
   - le modèle pivot (`ParsedActivity`) n'a aucune colonne de position.
3. **Aucun fichier original conservé** pour les nouveaux imports. Les FIT, GPX et TCX contiennent la trace : seule leur empreinte (`seen_files`) est gardée pour le dédoublonnage.
4. **Aucun export** :
   - la commande `ctrack export` et le bouton de l'interface sont supprimés ;
   - les boutons de téléchargement intégrés (image des graphiques, CSV des tableaux) sont masqués.
5. **Aucun affichage** : pas de carte. Les « sorties similaires » se cherchent sur la distance et le type, sans point de départ.
6. **Données existantes conservées au repos**, à la demande de l'utilisateur :
   - la migration 003 est **non destructive** ;
   - l'effacement définitif est une action volontaire : `ctrack purge-gps` (avec confirmation) supprime les colonnes GPS de la base, de la démo et des sauvegardes, avec `VACUUM` pour que rien ne subsiste dans le fichier, puis supprime `data/raw/`.
7. `PRAGMA secure_delete = ON` est actif sur toutes les connexions.

## Conséquences

- Plus de re-parsing de l'historique depuis les fichiers originaux. Les métriques se recalculent depuis les séries (`ctrack recompute`).
- **Limites hors de l'application** :
  - les données GPS anciennes restent lisibles par quiconque accède directement aux fichiers (`data/cadence.db`, `data/raw/`, sauvegardes) : c'est le rôle du chiffrement du disque (FileVault) et des droits du compte macOS ;
  - les noms d'activité donnés par Garmin contiennent souvent la ville (« Bordeaux Course à pied ») ;
  - le décalage horaire stocké donne une indication très grossière du fuseau.
