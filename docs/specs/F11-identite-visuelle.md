# F11 — Identité visuelle « Piste de nuit »

- **Statut** : ✅ livré (v0.1.1)
- **Code** : `ui/theme.py` (jetons, CSS, composants de marque), `ui/assets/` (logo), `.streamlit/config.toml` (thème Streamlit), `ui/charts.py` (`NIGHT`)
- **Tests** : `tests/test_ui_smoke.py` ; contrôle visuel par captures (bureau 1440 px, téléphone 390 px)

## Concept

L'interface s'inspire de l'univers de la course, pas d'un thème sombre générique :

- la **piste d'athlétisme bleue, la nuit**, qui donne les surfaces marine et les lignes de couloir couleur craie ;
- l'**horloge d'arrivée** et ses chiffres ambrés, qui donnent l'unique couleur forte de l'interface.

L'ambre signifie toujours « **votre valeur actuelle** » : le chiffre héros, la série principale, la semaine en cours, l'action principale. Tout le reste reste discret. Une seule touche de couleur vive, utilisée avec retenue.

## Jetons

| Nom | Hex | Rôle |
|---|---|---|
| Nuit | `#0B1624` | fond de page |
| Piste | `#122036` | cartes, champs |
| Relief | `#1A2B45` | en-têtes de tableau, infobulles |
| Couloir | `#24385A` | bordures, filets |
| Craie | `#EAF0F7` | texte principal, moyennes glissantes |
| Brume | `#9FB0C6` | texte secondaire, séries secondaires, tendances (pointillés) |
| Atténué | `#7D90A8` | légendes, axes (5:1 sur Piste) |
| **Chrono** | `#FFB020` | accent : votre valeur actuelle, actions principales |

**Couleurs de graphiques.** Elles ont été validées par `validate_palette.js` sur la surface `#122036` (mode sombre, toutes paires) :

- catégorielles : ambre `#C28400`, bleu couloir `#3B8EE6`, rose dossard `#D9628F` ;
- périodes ordonnées (de la plus ancienne à la plus récente) : `#8A5A0F` → `#B87814` → `#E59A18` → `#FFC14D`. La période la plus récente est la plus lumineuse.

**États.** Progrès `#45C98A`, alerte `#FF7B72`. Ils sont toujours accompagnés d'une flèche et d'un texte.

## Typographie

- **Titres, chiffres et logo** : *DIN Alternate*, police système d'Apple, avec *DIN Condensed* et *Avenir Next Condensed* en repli. C'est la police de la signalétique et des dossards, et aucun téléchargement n'est nécessaire.
- **Texte** : police système (SF Pro sur Mac et iPhone).
- Titres en casse de phrase. Pas d'étiquettes en capitales, pas de chasse fixe.

## Logo

`ui/assets/mark.svg` et `logo.svg`, une création originale :

- un « C » tracé par **deux couloirs de piste**, avec un point pour le coureur dans l'ouverture ;
- le tout sur une tuile ambre aux coins arrondis.

Le logotype « **Cadence** Tracker » est en DIN : « Cadence » en gras craie, « Tracker » en brume.

## Mise en page

- Navigation **en haut**, à côté du logo : Tableau de bord, Corrélations, Objectif, Sorties, Comparer, Réglages.
- **En-tête de page** : à droite, le sélecteur **Route / Trail** et, en mode Route, le menu **Type de séance**. Les choix sont conservés d'une page à l'autre (`persist_state="session"`).
- **En-tête de page** : un titre DIN, et en dessous une phrase qui décrit la sélection (« 112 sorties sur 6 mois, tous types de séance »).
- **Ouverture du tableau de bord : le chrono**.
  - La cadence médiane des 4 dernières semaines s'affiche en grands chiffres ambrés.
  - À côté, une bande de 12 barres hebdomadaires, comme les battements d'un métronome, dont la semaine en cours en ambre.
  - En dessous, un **couloir de progression** du point de départ vers l'objectif.
  - À droite, trois tuiles discrètes : allure, FC et volume.
- Les grilles CSS s'empilent sous 760 px. Vérifié à 390 px : aucun débordement horizontal.

## Règles

- Un seul accent vif. Les grands aplats (barres de volume, splits) restent en brume, et seule la valeur courante passe en ambre.
- Pas de dégradés, pas d'ombres décoratives, pas d'animation automatique.
- Les textes de l'interface sont des phrases (« Cadence médiane de 169 pas/min sur la première moitié… »), pas des chaînes de métadonnées séparées par des points.
- Le CSS personnalisé est minimal et localisé dans `theme.py`. On ne touche ni aux polices globales ni aux classes internes de Streamlit : la police d'icônes en dépend.
- `st.html` retire le SVG en ligne : les mini-graphiques sont donc passés en `<img>` avec une data-URI, et le couloir de progression est en CSS pur.

## Limites connues

- Hors des appareils Apple, DIN est remplacé par la police condensée disponible.
- Quelques libellés intégrés à Streamlit restent en anglais (bouton d'envoi de fichier).
