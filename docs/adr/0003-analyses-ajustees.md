# ADR 0003 — Mesurer la progression « à conditions égales » par régression multiple

- **Statut** : accepté (19/11/2026)

## Contexte

La cadence monte avec la vitesse, à raison d'environ 6 à 10 pas/min par m/s, et dépend aussi de la pente, du type de séance et de la fatigue. Une hausse brute de la cadence moyenne peut donc venir simplement de sorties plus rapides. Le projet demande explicitement de **distinguer une vraie progression d'une variation liée à l'allure ou au type de sortie**.

## Décision

1. L'effet du temps se mesure **à conditions égales** par une régression linéaire multiple (OLS, `statsmodels`), par exemple :
   `cadence ~ temps (mois) + vitesse + pente + C(type de séance)`.
2. L'unité d'analyse est le **kilomètre**. Les variations d'allure au sein d'une même sortie aident à identifier l'effet de la vitesse. Les km d'une même sortie n'étant pas indépendants, les **erreurs standard sont groupées par sortie** (*cluster-robust*).
3. On présente toujours l'**intervalle de confiance à 95 %**. La conclusion n'est « oui » ou « non » que si l'intervalle exclut zéro.
4. Pour l'objectif cadence, la cadence naturelle est **ajustée à une allure de référence**. La pente cadence/vitesse est estimée *au sein des sorties* (splits centrés par sortie).
5. L'interface rappelle à chaque fois qu'il s'agit d'**associations**, pas de causalité.

## Limites connues

- Les facteurs non mesurés (météo, chaussures, fatigue accumulée, sommeil) ne sont pas neutralisés.
- On suppose une relation linéaire : c'est raisonnable sur la plage d'allures d'un même coureur, moins vrai aux extrêmes (sprint).
- Le temps est modélisé linéairement. Pour une évolution non linéaire, la moyenne glissante sur 4 semaines reste l'indicateur visuel de référence.

## Évolutions possibles

Effets mixtes (`statsmodels.MixedLM`, effet aléatoire par sortie), splines sur le temps, ajout de la température (API météo) ou de la charge d'entraînement (ATL/CTL).
