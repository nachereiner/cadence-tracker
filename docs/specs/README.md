# Spécifications fonctionnelles

Chaque fonctionnalité a sa spec, versionnée avec le code. La règle : **une évolution fonctionnelle modifie d'abord sa spec** (comportement et critères d'acceptation), puis le code et les tests qui la vérifient.

| ID | Fonctionnalité | Statut |
|---|---|---|
| [F01](F01-import-synchronisation.md) | Import de fichiers et synchronisation Garmin | ✅ MVP |
| [F02](F02-stockage-dedoublonnage.md) | Stockage, dédoublonnage, idempotence | ✅ MVP |
| [F03](F03-normalisation-metriques.md) | Normalisation des séries et métriques par sortie | ✅ MVP |
| [F04](F04-tableau-de-bord.md) | Tableau de bord | ✅ MVP |
| [F05](F05-correlations.md) | Analyse des corrélations et questions clés | ✅ MVP |
| [F06](F06-classification.md) | Classification des séances | ✅ MVP |
| [F07](F07-objectif-cadence.md) | Objectif de cadence : progression, projection, date estimée | ✅ v0.2 |
| [F08](F08-sauvegarde.md) | Sauvegarde locale (aucun export, aucune donnée GPS) | ✅ v0.2.1 |
| [F09](F09-parametres.md) | Paramètres d'analyse | ✅ MVP |
| [F10](F10-comparaison.md) | Comparaison de sorties (jusqu'à 5) | ✅ v0.2 |
| [F11](F11-identite-visuelle.md) | Identité visuelle « Piste de nuit » (thème sombre, logo, mise en page) | ✅ v0.1.1 |

Statuts possibles : 📝 proposé · 🚧 en cours · ✅ livré · ♻️ à revoir.

## Modèle de spec

```markdown
# FXX — Titre
- **Statut** : … · **Code** : chemins · **Tests** : chemins

## Objectif            (le besoin utilisateur, en une ou deux phrases)
## Comportement         (ce que voit et fait l'utilisateur)
## Règles               (algorithmes, seuils, cas limites)
## Critères d'acceptation  (vérifiables ; idéalement un test chacun)
## Limites connues / évolutions
```
