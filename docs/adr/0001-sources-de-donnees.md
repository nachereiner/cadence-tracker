# ADR 0001 — Sources de données : API personnelle Garmin + fichiers, pas d'API Strava

- **Statut** : accepté (19/11/2026)
- **Contexte** : étude détaillée dans [`docs/research/sources-de-donnees.md`](../research/sources-de-donnees.md).

## Décision

1. La **synchronisation automatique** passe par l'**API personnelle officielle de Garmin** (client officiel `garmin-connect-personal-api-python`). Pour chaque course, on télécharge le **fichier FIT original**.
2. L'**import de fichiers** (FIT, TCX, GPX, ZIP imbriqués, gzip) est la solution de secours et le moyen de reprendre l'historique : export complet Garmin, export complet Strava, montre en USB.
3. **Pas d'API Strava.**
4. **Pas de bibliothèque Garmin non officielle.**

## Raisons

- Le FIT original est la donnée **la plus complète** (cadence fractionnaire, tours avec intensité, nom de l'entraînement) et **la même pour toutes les sources**. On n'écrit donc qu'un seul parser de référence.
- L'API personnelle Garmin est officielle, gratuite et sans validation. Elle s'authentifie par une clé révocable et n'expose pas les identifiants du compte.
- La politique API Strava du 01/06/2026 interdit de conserver les données plus de 7 jours (§6.2) et de constituer une base persistante (§5.5). C'est incompatible avec un suivi sur plusieurs années. Elle exige en plus un abonnement payant.
- Les bibliothèques non officielles ont été cassées pendant six mois en 2026. Elles manipulent le mot de passe Garmin et relèvent d'une zone grise des CGU.

## Conséquences

- Il faut créer une clé sur Garmin Connect, puis la renouveler à son expiration (1 an maximum).
- La profondeur d'historique de l'API n'est pas documentée : prévoir l'export complet Garmin pour l'historique ancien.
- Ajouter une source plus tard (Coros, Suunto, Polar…) revient à écrire un adaptateur qui produit un `ParsedActivity` ou télécharge un FIT. Le pipeline ne change pas.
- À réévaluer si Strava assouplit sa politique de stockage, ou si Garmin documente des quotas restrictifs.
