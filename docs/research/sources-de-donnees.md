# Étude : récupération automatique des données (Garmin, Strava, fichiers)

> Étude réalisée le **19/11/2026**. Les API évoluent vite (Garmin et Strava ont toutes deux changé leurs règles en 2026) : revérifier les points marqués ⚠️ avant toute évolution.

## Besoin

Pour chaque sortie, on veut **les séries temporelles**, pas seulement les totaux : temps, distance, vitesse, **cadence**, **fréquence cardiaque**, altitude, GPS (et les tours/laps si possible). On veut aussi une synchronisation incrémentale et idempotente, ainsi qu'un stockage local et durable.

## Synthèse

| Source | Accès | Séries temporelles | Stockage local long terme | Verdict |
|---|---|---|---|---|
| **Garmin — API personnelle officielle** (oct. 2026) | Gratuit, sans validation : clé créée sur Garmin Connect | ✅ via le **fichier FIT original** | ✅ (usage personnel) | **Source principale** |
| Garmin — export complet (« Exporter vos données ») | Manuel, gratuit | ✅ FIT originaux | ✅ | **Historique / secours** |
| Fichiers FIT/TCX/GPX (montre en USB, export unitaire) | Manuel | ✅ | ✅ | **Secours** |
| Strava — API v3 | Abonnement Strava payant requis pour créer l'app | ✅ streams | ❌ cache limité à 7 jours | **Écartée** |
| Strava — export complet (« Bulk export ») | Manuel, droit de l'utilisateur | ✅ fichiers originaux | ✅ | Import fichier possible |
| Garmin — bibliothèques non officielles (`python-garminconnect`) | Login par identifiants, rétro-ingénierie | ✅ | ✅ | **Écartée** (fragile, zone grise) |

## 1. Garmin Connect

### 1.1 API personnelle officielle (« Personal API ») — retenue

Garmin a ouvert fin octobre 2026 un palier **Personal** de son *Connect Developer Program*. Il est destiné à une personne qui lit ses propres données.

- **Obtention** : Garmin Connect (web) › Paramètres › *Personal API Key* (`https://connect.garmin.com/app/settings/personalApiToken`). Il n'y a ni dossier ni validation. On choisit la durée de validité : 30, 90 ou 180 jours, ou 1 an. Garmin prévient par e-mail environ une semaine avant l'expiration. Une seule clé est active à la fois, et elle n'est affichée qu'une fois. *(sources secondaires : appsforstrava, the5krunner)*
- **Authentification** : la clé est échangée contre un **jeton bearer JWT** valable environ 24 h, sans *refresh token* : on redemande un jeton avec la clé. **Vérifié dans le client officiel** : `POST https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token` avec l'en-tête `Authorization: ApiKey <clé>`.
- **Client Python officiel** : [`garmin/connect-personal-api-python`](https://github.com/garmin/connect-personal-api-python), paquet PyPI `garmin-connect-personal-api-python` 1.0.0, Apache 2.0, Python ≥ 3.12. Il met le jeton en cache dans un fichier en `0600`.
- **Endpoints utiles** (lus dans le code du client officiel) :
  - `GET /activitylist-service/activities/search/activities?start=&limit=&startDate=&endDate=&activityType=` : recherche paginée des activités. Champs utilisés : `activityId`, `activityName`, `activityType.typeKey`, `startTimeGMT`.
  - `GET /activity-service/activity/{id}` : résumé.
  - `GET /download-service/files/activity/{id}` : **fichier original (ZIP contenant le FIT)**. C'est lui qui porte les séries seconde par seconde : cadence, FC, vitesse, altitude, GPS, tours.
- **Contraintes** :
  - lecture seule, *pull* uniquement ;
  - ⚠️ **aucune limite de débit publiée**, et Garmin se réserve le droit de *throttler* sans préavis. Le client prévoit donc une pause entre téléchargements et des reprises sur HTTP 429/5xx ;
  - ⚠️ la **profondeur d'historique** accessible n'est documentée nulle part. Plan B : l'export complet Garmin ;
  - ⚠️ des développeurs signalent que les FIT livrés par l'API Garmin peuvent être expurgés de champs **non documentés** (VO2max, temps de récupération…). Les champs utiles ici (cadence, FC, vitesse, altitude, GPS) sont des champs **standard** du profil FIT et ne sont pas concernés.
- **Conditions** (*Personal API Supplemental Terms*, d'après sources secondaires) : la clé est réservée à son titulaire et aux outils qu'il développe ou exploite pour son propre usage. Elle ne doit être ni vendue ni partagée. Rien n'est dit sur le stockage local ni sur l'IA.
- Documentation de référence (Swagger) : `https://developer.garmin.com/gc-developer-program/personal/swagger-docs/` ⚠️ (inaccessible à l'outil d'étude, HTTP 403). C'est le premier document à relire si un endpoint change.

### 1.2 Export complet Garmin — retenu pour l'historique

Il se demande sur le compte Garmin (*Data Management › Export Your Data*) et arrive sous forme d'archive ZIP par e-mail. Les FIT originaux se trouvent dans des ZIP imbriqués (`DI_CONNECT/DI-Connect-Uploaded-Files/…`). L'outil lit directement ces ZIP imbriqués (`ctrack import archive.zip`).

### 1.3 Bibliothèques non officielles — écartées

- `garth` est **abandonné** depuis le 27/03/2026 : Garmin a modifié son flux d'authentification et le mainteneur ne l'adapte pas.
- `python-garminconnect` (0.3.20, 23/10/2026) fonctionne de nouveau. Il passe par une connexion SSO « mobile » qui imite l'app officielle avec `curl_cffi`. Mais il a été **cassé d'avril à octobre 2026**, il est exposé aux blocages Cloudflare (HTTP 429/427) et il manipule les identifiants du compte.
- Depuis l'existence de l'API personnelle officielle, ces bibliothèques n'apportent plus rien pour ce besoin.

## 2. Strava

### 2.1 API v3 — écartée

- **Accès** : depuis le 01/06/2026, **un abonnement Strava est requis pour créer une application**. Une nouvelle app est en « single player mode » : 1 athlète, extensible à 10 sans revue. *(developers.strava.com)*
- **Quotas** : 200 requêtes/15 min et 2 000/jour au total, dont 100/15 min et 1 000/jour en lecture. *(developers.strava.com/docs/rate-limits)*
- **Données** : `GET /activities/{id}/streams` reste disponible (time, distance, latlng, altitude, velocity_smooth, heartrate, cadence…). La cadence y est exprimée en foulées/min, donc ×2 pour obtenir des pas/min. La suppression d'endpoints du 01/09/2026 ne touche pas les activités. ⚠️ Le domaine de l'API change le 04/01/2027 (`api-v3.strava.com`).
- **Bloquant : la politique API du 01/06/2026** (`strava.com/legal/api_policy`) :
  - §6.2 : *« You may not retain Strava Data in your cache for longer than seven (7) days »*. Il n'y a **aucune exception** pour ses propres données ni pour une app personnelle ;
  - §5.5 : interdiction de constituer un index persistant, une archive ou une base accumulée par appels successifs ;
  - §5.3 : interdiction d'utiliser ces données avec une application d'IA, y compris en les injectant dans le contexte d'un modèle ;
  - §6.3 / §7.4 : suppressions à répercuter sous 48 h, et purge complète à l'arrêt.

  Un outil de suivi **sur le long terme** qui stocke l'historique est donc incompatible avec ces règles.

### 2.2 Export complet Strava — possible

Le §6.6 de la même politique garantit le droit de chaque utilisateur à exporter ses propres données via le *Bulk Data Export*. Ces fichiers ne passent pas par l'API. L'archive contient les fichiers originaux (`activities/*.fit.gz`, `*.gpx.gz`, `*.tcx.gz`), que l'outil sait importer, dédoublonnage compris.

## 3. Fichiers FIT / TCX / GPX

- **FIT** : le format natif des montres et le plus riche. On y trouve la cadence en foulées/min (`cadence` + `fractional_cadence`), la FC, la vitesse, l'altitude, le GPS, les tours (avec leur intensité *active/rest*) et le nom de l'entraînement structuré. Il est lu avec `fitdecode`.
- **TCX** : il porte la cadence (`RunCadence`), la vitesse, la FC et les tours.
- **GPX** : il ne porte que le GPS, l'altitude et le temps, plus la FC et la cadence via les extensions Garmin. La vitesse est recalculée à partir du GPS, avec moins de précision.
- Une montre Garmin récente branchée en USB passe par MTP sous macOS : il faut alors l'app Garmin Express ou Android File Transfer. Ce cas n'est pas prioritaire, puisque l'API couvre le besoin.

## 4. Recommandation

1. **Synchronisation automatique : API personnelle Garmin officielle.** On télécharge le **FIT original** de chaque course, que l'on archive et parse localement. La synchro est incrémentale : 3 jours de recouvrement, les identifiants déjà vus sont ignorés, et le curseur n'avance que si la synchro va au bout.
2. **Reprise de l'historique : export complet Garmin**, et/ou synchro complète (`ctrack garmin sync --full`) si l'API remonte assez loin ⚠️.
3. **Secours : import de fichiers** FIT/TCX/GPX/ZIP, y compris l'export complet Strava.
4. **Pas d'API Strava** tant que sa politique limite le stockage à 7 jours.

## Sources

- Client officiel Garmin : https://github.com/garmin/connect-personal-api-python (code lu : `constants.py`, `auth.py`, `client.py`)
- https://the5krunner.com/2026/10/22/garmin-personal-api/
- https://appsforstrava.com/blog/garmin-connect-developer-program-personal-api-key
- https://www.paincave.io/blog/garmin-api-changes-training-data-2026
- https://github.com/cyberjunky/python-garminconnect · https://github.com/matin/garth/discussions/222
- https://developers.strava.com/docs/rate-limits/ · https://developers.strava.com/docs/getting-started/ · https://developers.strava.com/docs/changelog/
- https://www.strava.com/legal/api · https://www.strava.com/legal/api_policy
