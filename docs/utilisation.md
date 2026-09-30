# Utiliser la console

Ouvrir http://127.0.0.1:8770, ou **Veille (V2)** sur http://127.0.0.1:8080/.

La colonne de gauche liste les veilles. Le chiffre sous le nom est la fenêtre en jours. Le bandeau du haut compte les articles et les sources en base, et lance **Rafraîchir les flux**.

## Lire une veille

Choisir une veille. Les pastilles `1 j`, `3 j`, `7 j`, `14 j`, `30 j` et `90 j` changent la période affichée et l’enregistrent pour cette veille. Les rubriques sous le titre filtrent la liste. Le champ de recherche ne parcourt que les titres déjà affichés.

Chaque carte montre le titre, la source, la date, les mots qui ont fait entrer l’article, et un extrait.

## Rafraîchir les flux

**Rafraîchir les flux** relit toutes les sources actives, pas seulement la veille ouverte. La barre du haut indique l’avancement. Pendant ce temps, les boutons de publication sont indisponibles.

À faire quand on veut des articles nouveaux. Inutile après un simple changement de mot-clé ou de fenêtre : le filtre est immédiat.

## Mots-clés

L’onglet **Mots** montre les rubriques et leurs mots.

- Taper un mot met à jour un compteur : ce que ce mot attrape déjà dans la base, pour la fenêtre de la veille.
- Choisir la rubrique, puis **Chercher**. Le mot est ajouté à la rubrique. Google News est interrogé tout de suite et les articles trouvés arrivent dans la veille.
- Sous le résultat, les sites nouveaux cités par ces articles ont un bouton **Trouver le flux**. Il cherche le RSS du site et le propose dans l’onglet Radar.
- La croix d’une pastille retire le mot. Les articles déjà en base sont refiltrés aussitôt.

## Vue 3D

Le bouton **3D**, à côté de Mots, Radar et Sources, ouvre une fenêtre. Le nom de la veille reste au centre. Autour, les rubriques forment des groupes, et les mots-clés de chaque rubrique tournent avec elles. La taille d’un mot suit le nombre d’articles de la fenêtre en cours. Glisser fait tourner la vue, la molette rapproche, **Rotation** relance le mouvement automatique. Un clic sur un mot-clé ouvre à droite les résumés des articles trouvés ; le titre ouvre l’article dans un autre onglet. Échap ou **Fermer** quitte la fenêtre.

## Radar

L’onglet **Radar** cherche de nouveaux flux pour la veille affichée. **Lancer le radar** interroge Google News et le web avec les mots des rubriques, puis ne garde que les flux dont les titres collent au sujet.

Chaque proposition montre le nom du flux, pourquoi il a été retenu, et quelques titres.

- **Ajouter le flux** l’enregistre dans le catalogue commun et le lit une première fois.
- **Écarter** le retire des propositions. Il ne sera pas reproposé.

Le détail du classement est dans [sources.md](sources.md).

## Créer une veille

En bas de la colonne de gauche, saisir un nom et **Créer**. La veille démarre avec une rubrique Général, une fenêtre de 7 jours, et les articles du catalogue qui correspondent aux mots qu’on y ajoute.

## Publier

Sous le titre de la veille :

| Bouton | Effet |
| --- | --- |
| PDF, HTML, MD | Dépose ce format pour la veille ouverte, sur la fenêtre affichée |
| Toutes les veilles | Dépose les trois formats de chaque veille, chacune avec sa fenêtre enregistrée |

À la fin, la console donne le lien du fichier et celui de la page [Veille 2](https://f4eed.pages-perso.free.fr/Veille_2/). Le dépôt peut prendre plusieurs minutes quand toutes les veilles partent ensemble. Voir [publication.md](publication.md).
