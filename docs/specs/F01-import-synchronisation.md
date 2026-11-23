# F01 — Import de fichiers et synchronisation Garmin

- **Statut** : ✅ MVP
- **Code** : `ingest/files.py`, `ingest/fit.py`, `ingest/xml_formats.py`, `ingest/garmin.py`, `cli.py`, `ui/views/data.py`
- **Tests** : `tests/test_parsers.py`, `tests/test_garmin_sync.py`
- **Décision** : [ADR 0001](../adr/0001-sources-de-donnees.md)

## Objectif

Récupérer automatiquement et sans doublon les courses, **avec leurs séries temporelles**. Les fichiers servent de solution de secours.

## Comportement

### Synchronisation Garmin (API personnelle officielle)

1. L'utilisateur crée une clé sur Garmin Connect (*Paramètres › Personal API Key*).
2. Il l'enregistre avec `ctrack garmin set-key` (saisie masquée) ou depuis **Réglages › Import et synchronisation**. La clé est stockée dans le trousseau du système.
3. Il lance `ctrack garmin sync`, le bouton **« Synchroniser mes nouvelles sorties »** de la page Sorties, ou celui de **Réglages › Import et synchronisation**. Ce dernier offre trois modes :
   - *Nouvelles activités* (par défaut) : depuis la dernière activité synchronisée moins 3 jours ;
   - *Depuis une date* : `--since AAAA-MM-JJ` ;
   - *Tout l'historique* : `--full`, éventuellement borné par le paramètre `garmin_history_start`.
4. Un compte rendu s'affiche : activités listées, courses, déjà synchronisées, téléchargées, importées.

### Import de fichiers

- CLI : `ctrack import <fichiers|dossiers|archives…>`, récursif.
- UI : dépôt de fichiers multiples (jusqu'à 1 Go par envoi, `.streamlit/config.toml`).
- Formats : `.fit`, `.tcx`, `.gpx`, leurs versions `.gz`, et `.zip`, y compris imbriqués (export complet Garmin, export Strava). Le format est détecté sur le **contenu** (en-tête `.FIT`, racine XML), le nom ne sert qu'en dernier recours.

### Choix des activités prises en compte

Chaque sortie peut être **exclue des analyses** (case « Inclure » de la liste de la page Sorties). Une sortie exclue reste stockée et visible, mais elle n'entre plus dans aucun calcul.

## Règles

- Seules les **courses** sont importées : sport FIT `running` (sous-sports route, trail, tapis, piste) et `typeKey` Garmin `running`, `trail_running`, `treadmill_running`, `track_running`, `street_running`, `indoor_running`, `virtual_run`, `ultra_run`, `obstacle_run`. Le reste est ignoré avec le statut `skipped`.
- Une activité de moins de 2 minutes est ignorée.
- Garmin :
  - échange de la clé contre un jeton d'environ 24 h, mis en cache en `0600` dans `~/.config/cadence-tracker/` ;
  - en cas de HTTP 401, le jeton est renouvelé une fois ;
  - en cas de HTTP 429 ou 5xx, jusqu'à 3 reprises avec une attente de 30, 60 puis 90 s ;
  - une pause de 0,5 s sépare deux téléchargements ;
  - une activité dont l'`activityId` est déjà connu (comme activité ou comme fichier brut) n'est **pas retéléchargée** ;
  - **le curseur n'avance que si la synchro est allée au bout** : une synchro interrompue reprend la même fenêtre la fois suivante.
- Le nom Garmin (`activityName`) devient le nom de la sortie : le FIT n'en contient pas.
- **La catégorie Garmin fait foi** (`typeKey`) : une activité classée course dans Garmin est importée comme course, même si son fichier dit autre chose. C'est le cas d'un vieux GPX marqué « hiking ». Le sous-sport en découle aussi (`trail_running` donne trail, `treadmill_running` donne tapis).
- Garmin renvoie le **fichier d'origine**. C'est un FIT pour les activités enregistrées par la montre, mais parfois un **GPX** pour les activités importées d'une autre application. Ces GPX ne contiennent ni cadence ni FC : ces sorties comptent dans le volume, pas dans les analyses de cadence.
- Toute activité ignorée (autre sport, trop courte) est inscrite au journal des imports avec la raison.
- **Ni le fichier téléchargé ni ses positions GPS ne sont conservés** : seules les séries utiles (temps, distance, vitesse, cadence, FC, altitude) et l'empreinte du fichier sont stockées (ADR 0004).
- Une erreur de lecture sur un fichier n'interrompt jamais un lot. Elle est journalisée avec le statut `error`.

## Critères d'acceptation

- [x] Un FIT est lu avec ses canaux (cadence avec partie fractionnaire, FC, vitesse, altitude, GPS en degrés), son sous-sport et son décalage horaire. → `test_fit_parsing_reads_channels_and_metadata`
- [x] TCX et GPX (extensions Garmin) sont lus. → `test_tcx_parsing`, `test_gpx_with_garmin_extensions`
- [x] Un ZIP contenant un ZIP de FIT et un `.gpx.gz` est entièrement importé. → `test_archives_are_expanded_recursively`
- [x] Une synchro Garmin importe les courses, ignore le vélo et ne retélécharge rien au second passage. → `test_sync_imports_running_activities_once`
- [x] Un HTTP 429 déclenche une attente puis une reprise. → `test_rate_limit_is_retried`
- [x] Une synchro interrompue ne fait pas avancer le curseur. → `test_interrupted_sync_keeps_previous_cursor`

## Limites connues / évolutions

- ⚠️ À vérifier sur le compte réel : profondeur d'historique de l'API personnelle, quotas, et forme exacte des réponses (`startTimeGMT` en particulier).
- La clé expire au bout d'un an au plus : prévoir un rappel. Évolution : lire la date d'expiration du jeton et avertir dans l'UI.
- Synchro planifiée : un `launchd`/`cron` qui lance `ctrack garmin sync` chaque matin (voir le README).
- Autres sources (Coros, Polar, Suunto) : un adaptateur qui télécharge un FIT et appelle `import_raw`.
