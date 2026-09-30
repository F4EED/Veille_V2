# Les veilles

Au premier lancement, sept veilles sont copiées depuis `C:\Apps\veille_techno\config`. Elles lisent le même catalogue de sources. Chacune ne montre que les articles qui correspondent à ses rubriques.

Les mots-clés d’origine viennent des fichiers `keywords*.yaml`. Après l’import, on les modifie dans la console. Ces fichiers ne sont plus relus.

Une veille créée dans la console s’ajoute à la liste. Son fichier publié s’appelle `Veille_` suivi du nom, en caractères simples. Elle a au départ une rubrique Général et une fenêtre de 7 jours.

## Veilles importées

| Veille | Fenêtre d’origine | Périmètre |
| --- | --- | --- |
| IoT | 7 jours | Objets connectés, LoRa, mesh, routes, radio |
| Crise | 7 jours | Risques, alertes, aléas, gestion de crise |
| Radio | 7 jours | Radioamateur, modes digitaux, SDR, trafic |
| Outils PC | 7 jours | Logiciels de crise et poste de commandement |
| Black-out | 14 jours | Réseau électrique, délestage, résilience |
| Géomatique | 7 jours | QGIS, cartographie, lidar, données géographiques |
| Mesh | 7 jours | Meshtastic, MeshCore, firmwares et mesh Wi-Fi |

L’ordre dans la colonne de gauche est celui du tableau, puis les veilles créées ensuite.

Le découpage en rubriques (domaines et priorités) est celui des fichiers de mots-clés de la veille d’origine au moment de l’import. Le descriptif rubrique par rubrique de cette veille reste dans `C:\Apps\veille_techno\docs\profils.md`.

## Fenêtre

La fenêtre affichée à côté du nom est celle utilisée par **Toutes les veilles**. Les boutons PDF, HTML et MD de la veille ouverte utilisent la pastille sélectionnée à l’écran, qui est la même valeur une fois le clic enregistré.

Les choix possibles sont 1, 3, 7, 14, 30 et 90 jours.

## Fichiers publiés

| Veille | Nom de fichier |
| --- | --- |
| IoT | `Veille_IOT.pdf`, `.html`, `.md` |
| Crise | `Veille_Crise` |
| Radio | `Veille_Radio` |
| Outils PC | `Veille_Outils_PC` |
| Black-out | `Veille_Blackout` |
| Géomatique | `Veille_Geomatique` |
| Mesh | `Veille_Mesh` |

Ils sont déposés dans le dossier `Veille_2` des Pages Perso. Voir [publication.md](publication.md).
