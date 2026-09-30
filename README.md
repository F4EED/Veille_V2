# Veille 2

Console locale de veille. Les flux sont lus une fois, en parallèle, et rangés dans une base. Chaque veille est un filtre immédiat sur ces articles : changer un mot-clé ou la fenêtre de jours ne relance pas la collecte.

Le catalogue et les mots-clés de `C:\Apps\veille_techno` sont copiés au premier lancement dans `data\veille.sqlite`. Ensuite, les mots-clés, les veilles créées ici et les flux ajoutés par le radar restent dans cette base. Les fichiers YAML de la veille d’origine ne sont pas réécrits.

Sept veilles sont importées :

| Profil | Fichier publié | Thème |
| --- | --- | --- |
| `iot` | `Veille_IOT` | Objets connectés, LoRa, mesh, routes, radio |
| `crise` | `Veille_Crise` | Risques, alertes, aléas, gestion de crise |
| `radio` | `Veille_Radio` | Radioamateur, modes digitaux, SDR, trafic |
| `outils` | `Veille_Outils_PC` | Logiciels de crise et poste de commandement |
| `blackout` | `Veille_Blackout` | Réseau électrique, délestage, résilience |
| `geomatique` | `Veille_Geomatique` | QGIS, cartographie, lidar, données géographiques |
| `mesh` | `Veille_Mesh` | Meshtastic, MeshCore, firmwares et mesh Wi-Fi |

On peut en créer d’autres dans la console. Le détail est dans [docs/profils.md](docs/profils.md).

## Lancer

Python 3, puis un double-clic sur `lancer.bat`, ou :

```bat
py -3 -m veille_v2
```

La console écoute sur http://127.0.0.1:8770

Depuis le portail http://127.0.0.1:8080/, l’entrée **Veille (V2)** ouvre cette adresse et démarre le programme si le port est libre.

L’installation, le premier import et les dépendances sont dans [docs/installation.md](docs/installation.md).

## Documentation

- [Installer et lancer](docs/installation.md)
- [Comprendre le fonctionnement](docs/comprendre.md)
- [Utiliser la console](docs/utilisation.md)
- [Les veilles](docs/profils.md)
- [Sources, mots-clés et radar](docs/sources.md)
- [Publier en PDF, HTML et Markdown](docs/publication.md)

Le courriel du matin et les rapports déposés dans le dossier `veille` restent ceux de `C:\Apps\veille_techno`. Veille 2 publie à part, dans [Veille 2](https://f4eed.pages-perso.free.fr/Veille_2/).

## Fichiers du programme

| Fichier | Rôle |
| --- | --- |
| `lancer.bat` | Démarre la console sous Windows |
| `veille_v2/serveur.py` | Pages et API sur le port 8770 |
| `veille_v2/collecte.py` | Téléchargement parallèle des flux |
| `veille_v2/filtre.py` | Filtre une veille sur les articles déjà en base |
| `veille_v2/decouverte.py` | Recherche d’un mot et radar de nouveaux flux |
| `veille_v2/export.py` | PDF, HTML, Markdown et dépôt FTP |
| `veille_v2/magasin.py` | Base SQLite |
| `veille_v2/seed.py` | Import unique du catalogue de la veille d’origine |
| `web/` | Interface de la console |
| `data/veille.sqlite` | Articles, veilles, mots-clés, sources |
| `data/publications.json` | Derniers fichiers déposés sur les Pages Perso |
