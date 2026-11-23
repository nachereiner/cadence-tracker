# ADR 0002 — Stack : Python, SQLite, Streamlit + Plotly

- **Statut** : accepté (19/11/2026)

## Décision

- **Python 3.12+** pour tout le projet, géré avec `uv`. Le client Garmin officiel impose Python 3.12.
- **SQLite** (mode WAL) pour le stockage : un seul fichier, sauvegardable à chaud.
- **Streamlit** pour l'interface et **Plotly** pour les graphiques interactifs.
- **pandas / numpy / scipy / statsmodels** pour les calculs et les statistiques ; **fitdecode** pour le FIT.
- **Typer** pour la ligne de commande, **keyring** pour les secrets.

## Alternatives considérées

| Option | Pour | Contre |
|---|---|---|
| FastAPI + SPA (React/Svelte) + ECharts | UX sur mesure, très réactive | deux langages, une chaîne de build, environ 2× plus de code à maintenir |
| Dash | callbacks fins | plus verbeux que Streamlit pour un gain faible ici |
| DuckDB | analytique très rapide | un seul processus écrivain : conflit entre l'UI et une synchro en ligne de commande |
| Notebook Jupyter | exploration libre | pas une application utilisable au quotidien, ni sur smartphone |

## Raisons

- C'est un outil **personnel**, à maintenir sur des années par une seule personne : un langage unique et un minimum de pièces.
- Plotly offre le zoom, le survol unifié et les axes partagés (courbes synchronisées), et fonctionne au tactile.
- Streamlit est responsive : les colonnes s'empilent sur mobile, et le thème clair ou sombre suit le système.
- Le cœur (`ingest`, `storage`, `analysis`) est indépendant de Streamlit. Si l'UI devient limitante, on peut la remplacer sans réécrire la logique.

## Conséquences

- Chaque interaction ré-exécute la page. Les données sont donc mises en cache (`st.cache_data`) avec pour clé une empreinte de la base.
- Une personnalisation visuelle poussée reste limitée. C'est accepté pour le MVP.
