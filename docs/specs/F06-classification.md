# F06 — Classification des séances

- **Statut** : ✅ MVP
- **Code** : `analysis/classification.py`, `ingest/pipeline.py` (`reclassify`), `ui/views/activities.py`, `ui/views/detail.py` (onglet Annotations)
- **Tests** : `tests/test_classification.py`

## Objectif

Isoler les sorties comparables (en particulier l'**endurance fondamentale**) pour étudier la progression technique sans mélanger les intensités.

## Types

`ef` Endurance fondamentale · `long` Sortie longue · `intervals` Fractionné / VMA · `tempo` Seuil / tempo · `trail` Trail · `other` Autre.

## Règles automatiques

La première règle qui s'applique l'emporte, et la raison est affichée dans l'UI.

1. **Mots-clés** dans le nom de la sortie ou de l'entraînement, sans tenir compte des accents ni de la casse :
   - seuil / tempo / threshold / allure spécifique (« Allure 21 », AS10, semi, marathon) : `tempo` ;
   - fractionné / VMA / interval / « 10x400 » / côtes / force : `intervals` ;
   - sortie longue / SL / long run : `long` ;
   - EF / endurance / footing / easy / récup / facile / base : `ef` ;
   - trail : `trail`, en **dernier** : dans « TRAIL-S2-1-Endurance Fondamentale », le mot « TRAIL » est le nom du plan et la séance est une EF (le terrain est déjà connu par le sous-sport).
2. **Trail** : sous-sport FIT `trail`, ou D+ ≥ 25 m/km.
3. **Séance structurée** (tours *active* et *rest* de la montre) : répétitions de 6 min ou plus, `tempo` ; au moins 3 répétitions de 30 s ou plus, `intervals`. Des lignes droites de 15 s ne suffisent pas.
4. **Accélérations répétées** : au moins 4 efforts tenus 30 s (`fast_blocks`) **et** une variabilité d'allure hors arrêts ≥ 0,10 donnent `intervals`. Les arrêts aux feux d'une sortie en ville ne déclenchent plus cette règle.
5. **Seuil** : FC moyenne ≥ 86 % de la FC max pendant au moins 15 min.
6. **Sortie longue** : durée ≥ 80 min ou distance ≥ 16 km.
7. **EF** : FC moyenne ≤ 80 % de la FC max. Sans FC : allure ≤ allure médiane habituelle + 2 %.
8. Sinon `other`.

La **FC max** est un paramètre. À défaut, elle est estimée comme le plus haut pic de FC sur 30 s observé, entre 120 et 225 bpm. Tous les seuils sont réglables (F09).

## Correction manuelle

- Page **Sorties** : le bouton **« Synchroniser mes nouvelles sorties »** en haut, puis la liste des sorties, **repliée par défaut**. Une fois dépliée, c'est un tableau éditable (nom, type de séance, case « Inclure ») enregistré par un bouton. La liste suit le mode Route/Trail.
- Le type manuel est stocké à part (`session_type_manual`) et **n'est jamais écrasé** par une reclassification. Revenir au type automatique efface le choix manuel.
- La reclassification automatique tourne après chaque import et après chaque changement de paramètres.

## Calage sur données réelles (19/11/2026)

Les règles ont été testées sur les données, sans les noms, face aux 30 séances nommées par le plan d'entraînement :
- 6 VMA sur 6 et 8 EF sur 9 sont retrouvées ;
- les séances de seuil structurées sont souvent vues comme du fractionné, mais leur nom les corrige ;
- l'ancienne règle de variabilité (sans exclure les arrêts) classait 43 sorties libres en ville comme du fractionné.

## Critères d'acceptation

- [x] Les mots-clés sont reconnus, accents compris, et « Seuil 3x10' » donne `tempo`. → `test_keywords_win_and_are_accent_insensitive`
- [x] Chaque règle de données produit le type attendu. → `test_rules_from_data`
- [x] La FC max est estimée quand elle n'est pas réglée. → `test_hr_max_is_estimated_when_not_set`
- [x] Une sortie sans nom (NULL) est classée sans erreur. → `test_missing_names_are_handled`
- [x] Une correction manuelle survit à une réimportation plus riche. → `tests/test_pipeline.py::test_richer_version_replaces_data_but_keeps_annotations`

## Évolutions

- Zones de FC personnalisées (seuils LT1/LT2) plutôt qu'en % de la FC max.
- Utiliser le type d'entraînement Garmin (`workout`) quand il est présent.
- Classifieur appris sur les corrections manuelles, une fois qu'il y en aura assez.
