# Sécurité

## Signaler une faille

Merci de **ne pas ouvrir d'issue publique**. Utilisez plutôt le signalement privé de GitHub : onglet **Security › Report a vulnerability** de ce dépôt.

Indiquez si possible la version (commit) concernée, les étapes pour reproduire et l'impact possible.

## Périmètre

Cadence Tracker est une application **locale** : chaque utilisateur l'installe sur son propre poste, et l'interface n'écoute que sur `127.0.0.1`. Sont notamment dans le périmètre :

- la lecture de fichiers d'activité piégés (FIT, TCX, GPX, ZIP) ;
- la fuite de la clé Garmin ou du jeton temporaire ;
- tout moyen d'exposer l'interface ou les données au-delà du poste local ;
- une dépendance vulnérable utilisée par l'application.

Seule la dernière version de la branche `main` est maintenue.
