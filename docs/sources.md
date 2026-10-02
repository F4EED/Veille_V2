# Sources, mots-clés et radar

## Mots-clés

Chaque veille a des rubriques. Une rubrique a une priorité et une liste de mots. Les tendances sont des étiquettes en plus : elles ne font pas entrer un article toutes seules.

Dans une rubrique, les mots se combinent par OU. L’article va dans la rubrique de plus haute priorité qui correspond. S’il ne correspond à aucune, il n’apparaît pas dans cette veille.

La comparaison ignore les accents. Un mot seul est cherché comme mot entier. Une expression, ou un terme avec un trait d’union, est cherchée en entier dans le texte.

Ajouter ou retirer un mot dans l’onglet **Mots** met à jour la base tout de suite. Le fichier YAML d’origine n’est pas modifié.

## Catalogue

Les sources vivent dans `data\veille.sqlite`, table `sources`. L’import initial reprend `C:\Apps\veille_techno\config\sources.yaml` et `reseaux_sociaux.yaml`.

| Type | Rôle |
| --- | --- |
| Flux RSS ou Atom | Lu à chaque **Rafraîchir les flux**. Avec `mots_cles`, seules les veilles dont un mot correspond gardent l’article |
| Google News | Une recherche égale un flux. Celles du catalogue gardent leur filtre d’origine |
| Recherche lancée par **Chercher** | Flux Google News de la veille ouverte, filtre `aucun`, rangé dans la rubrique choisie |
| X, Instagram, Snap | À chaque rafraîchissement, les mots-clés des rubriques sont cherchés sur ces réseaux via Google News, en français et en anglais |
| WMS | Enregistré, non téléchargé comme un fil d’articles |
| Flux ajouté par le radar | `mots_cles`, visible par toutes les veilles, chacune filtrant avec ses mots |
| HCFRN | Flux `https://www.hcfrn.org/blog-feed.xml`, site https://www.hcfrn.org/. Lu comme les autres flux RSS |

L’onglet **Sources** liste le catalogue, les erreurs de lecture en tête.

## X, Instagram et Snap

À chaque **Rafraîchir les flux**, les mots-clés des rubriques (toutes les veilles, y compris celles créées dans la console) sont cherchés sur X (`x.com` et `twitter.com`), Instagram et Snap. La recherche passe par Google News, en français et en anglais, par paquets de mots. Un mot ajouté ou retiré est donc pris au rafraîchissement suivant.

Les articles trouvés entrent dans une veille seulement si un de ses mots-clés correspond, comme pour les autres flux. Les recherches X déjà importées du catalogue d’origine restent en plus.

Snap et Instagram n’exposent pas un flux des publications. Seules les pages reprises par Google News remontent.

## Chercher un mot

**Chercher** fait deux choses :

1. Il ajoute le mot à la rubrique choisie.
2. Il télécharge le flux Google News français de ce mot et range les articles dans la veille ouverte.

Le compteur affiché avant le clic ne compte que ce qui est déjà en base. Les sites nouveaux cités par les articles récupérés peuvent être sondés avec **Trouver le flux**.

## Radar

**Lancer le radar** travaille pour la veille affichée.

1. Il choisit jusqu’à six mots caractéristiques, un par rubrique quand c’est possible : un nom court (MeshCore, QGIS, Meshtastic) plutôt qu’une longue phrase.
2. Il interroge Google News en français. Si le mot est sans accent, il interroge aussi l’anglais.
3. Il interroge le web avec ce mot accompagné de `rss` ou `feed`.
4. Il reprend les éditeurs déjà présents dans les articles Google News, réseaux et recherches, s’ils ne sont pas déjà au catalogue.
5. Pour chaque site retenu, il cherche un flux : lien RSS ou Atom de la page, adresse du type `/feed` ou `/rss.xml`, et `releases.atom` pour un dépôt GitHub.
6. Il ne propose le flux que si des titres récents, ou le titre du flux, correspondent aux mots de la veille.

Un site déjà dans les sources, déjà proposé ou déjà écarté est ignoré. Sur GitHub, GitLab, Codeberg, Medium, Substack, Blogspot et WordPress.com, c’est le dépôt ou le blog qui est comparé, pas tout le domaine.

**Ajouter le flux** l’inscrit au catalogue et le lit une fois. **Écarter** le mémorise pour ne plus le proposer. **Trouver le flux**, depuis l’onglet Mots, sond le site demandé même si les titres ne collent pas encore aux mots de la veille : la proposition indique alors que le flux a été trouvé sans correspondance.
