# Veille 2

Version actuelle : **2.1.1**. L’historique est dans [CHANGELOG.md](CHANGELOG.md).

Console locale de veille technologique et de crise. Elle tourne sur le poste, à l’adresse http://127.0.0.1:8770. Les Pages Perso ne font qu’afficher les rapports déjà déposés : https://f4eed.pages-perso.free.fr/Veille_2/

Le principe est simple. Les flux sont lus **une fois**, en parallèle, et rangés dans `data\veille.sqlite`. Chaque veille est ensuite un filtre immédiat sur cette base. Changer un mot-clé, une rubrique ou la fenêtre de jours réaffiche les articles déjà collectés. Seul **Rafraîchir les flux**, **Chercher** ou l’ajout d’un nouveau flux relance un téléchargement.

Le catalogue et les mots-clés de `C:\Apps\veille_techno` sont copiés au premier lancement. Ensuite, les mots-clés, les veilles créées dans la console et les flux ajoutés par le radar restent dans SQLite. Les fichiers YAML de la veille d’origine ne sont pas réécrits.

Le courriel du matin et les rapports du dossier `veille` restent ceux de `C:\Apps\veille_techno`. Veille 2 publie à part, dans le dossier FTP `Veille_2`, et peut envoyer elle-même un courriel dont le contenu se choisit adresse par adresse.

## Veille d’origine et Veille 2

| | Veille d’origine | Veille 2 |
| --- | --- | --- |
| Dossier | `C:\Apps\veille_techno` | `C:\Apps\Veille_V2` |
| Lancement | Sept profils l’un après l’autre, souvent à 7 h | Console permanente, port 8770 |
| Collecte | Une passe par veille | Une passe pour toutes les veilles |
| Mots-clés | Fichiers `keywords*.yaml` | Base SQLite, modifiables dans l’interface |
| Lecture | Rapport produit à la fin de la passe | Liste filtrée tout de suite dans le navigateur |
| Formats | PDF et HTML, plus le courriel du matin | PDF, HTML et Markdown, et un courriel choisi adresse par adresse |
| Publication | https://f4eed.pages-perso.free.fr/veille/ | https://f4eed.pages-perso.free.fr/Veille_2/ |

## Veilles importées

Au premier démarrage, sept veilles sont copiées depuis `C:\Apps\veille_techno\config`. Elles lisent le même catalogue. Chacune ne montre que les articles qui correspondent à ses rubriques.

| Profil | Titre | Fichier publié | Fenêtre de repli | Thème |
| --- | --- | --- | --- | --- |
| `iot` | IoT | `Veille_IOT` | 7 jours | Objets connectés, LoRa, mesh, routes, radio |
| `crise` | Crise | `Veille_Crise` | 7 jours | Risques, alertes, aléas, gestion de crise |
| `radio` | Radio | `Veille_Radio` | 7 jours | Radioamateur, modes digitaux, SDR, trafic |
| `outils` | Outils PC | `Veille_Outils_PC` | 7 jours | Logiciels de crise et poste de commandement |
| `blackout` | Black-out | `Veille_Blackout` | 14 jours | Réseau électrique, délestage, résilience |
| `geomatique` | Géomatique | `Veille_Geomatique` | 7 jours | QGIS, cartographie, lidar, données géographiques |
| `mesh` | Mesh | `Veille_Mesh` | 7 jours | Meshtastic, MeshCore, firmwares et mesh Wi-Fi |

La fenêtre réellement importée est `periode_jours` dans le fichier de mots-clés, quand cette valeur est présente. Le repli du tableau s’applique sinon. On peut la changer ensuite dans la console : 1, 3, 7, 14, 30 ou 90 jours. La valeur affichée à côté du nom est celle qu’utilise **Toutes les veilles**.

L’ordre dans la colonne de gauche est celui du tableau, puis les veilles créées dans la console. Une veille créée ici démarre avec une rubrique Général, une fenêtre de 7 jours, et un fichier `Veille_` suivi du titre en caractères simples. Elle entre dans le rafraîchissement et dans l’export de toutes les veilles dès qu’elle existe. Sans mot-clé, elle ne montre rien.

Le découpage rubrique par rubrique au moment de l’import est celui des YAML d’origine. Le descriptif de cette veille reste dans `C:\Apps\veille_techno\docs\profils.md`. Ici : [docs/profils.md](docs/profils.md).

## Installer

Il faut Windows, Python 3 (`py -3` ou `python`), et le dossier `C:\Apps\veille_techno` pour le premier import et pour le mot de passe FTP déjà utilisé par la veille d’origine. Les PDF utilisent Georgia et Calibri, présentes dans `C:\Windows\Fonts`.

Les bibliothèques déclarées sont `feedparser` et `PyYAML` (`requirements.txt`). La fabrication des PDF s’appuie en plus sur `fpdf2`, déjà fourni avec la veille d’origine.

Si `C:\Apps\veille_techno\.vendor` existe, Veille 2 l’ajoute à son chemin Python. Sinon, dans `C:\Apps\Veille_V2` :

```bat
py -3 -m pip install -r requirements.txt
```

Le mot de passe FTP n’est pas dans ce dossier. La publication lit :

- `C:\Apps\veille_techno\config\email.yaml`, bloc `publication` (`hote`, `utilisateur`)
- `C:\Apps\veille_techno\config\email.secrets.yaml`, clé `mot_de_passe`

Le serveur par défaut est `ftpperso.free.fr`. L’identifiant Free est le login Pages Perso, sans `@`. Le dossier distant est `Veille_2`. S’il n’existe pas, il est créé au premier dépôt.

Détail : [docs/installation.md](docs/installation.md).

## Lancer

Double-clic sur `lancer.bat`, ou :

```bat
cd /d C:\Apps\Veille_V2
py -3 -m veille_v2
```

`lancer.bat` essaie `py -3`, puis `python` si la première commande échoue. La console affiche `Veille vive : http://127.0.0.1:8770`. Ouvrir cette adresse.

Au premier démarrage, le programme copie dans `data\veille.sqlite` :

- les sept veilles et leurs mots-clés (`config\keywords*.yaml`)
- les flux RSS, les recherches Google News et les réseaux du catalogue (`sources.yaml`, `reseaux_sociaux.yaml`)
- les services WMS, enregistrés mais non lus comme des articles

Cet import n’a lieu qu’une fois (`meta.seed`). Modifier les YAML ensuite ne change pas la console.

Depuis le portail http://127.0.0.1:8080/, l’entrée **Veille (V2)** ouvre http://127.0.0.1:8770/. Si le port est libre, **Ouvrir** lance `python -m veille_v2` dans `C:\Apps\Veille_V2`. Si la console tourne déjà, le lien s’ouvre directement.

Pour arrêter : fermer la fenêtre de commande qui a lancé `lancer.bat`, ou quitter le processus Python qui écoute sur le port 8770. Fermer le navigateur laisse la console en marche. La base reste sur le disque.

## Utiliser la console

La colonne de gauche liste les veilles. Le bandeau du haut compte les articles et les sources en base, et lance **Rafraîchir les flux**. Sous le titre : la fenêtre en jours, les boutons de publication, puis la liste d’articles. À droite : les onglets **Mots**, **Radar**, **Sources**, et le bouton **3D**.

### Lire une veille

Choisir une veille. Les pastilles `1 j`, `3 j`, `7 j`, `14 j`, `30 j` et `90 j` changent la période affichée et l’enregistrent pour cette veille. Les rubriques sous le titre filtrent la liste. Le champ de recherche ne parcourt que les titres déjà affichés.

Chaque carte montre le titre, la source, la date, les mots qui ont fait entrer l’article, et un extrait.

### Rafraîchir les flux

**Rafraîchir les flux** relit toutes les sources actives, pour toutes les veilles, pas seulement celle qui est ouverte. Jusqu’à 24 téléchargements avancent en parallèle. Google News est limité pour ne pas saturer le service. La barre du haut indique l’avancement. Pendant une collecte ou une publication, les boutons d’export sont indisponibles.

À faire quand on veut des articles nouveaux. Inutile après un simple changement de mot-clé ou de fenêtre.

Au début de chaque rafraîchissement, les mots-clés de toutes les rubriques (toutes les veilles, y compris celles créées dans la console) sont recherchés sur X, Instagram et Snap. Voir plus bas.

### Mots-clés

L’onglet **Mots** montre les rubriques et leurs mots.

- Taper un mot met à jour un compteur : ce que ce mot attrape déjà dans la base, pour la fenêtre de la veille.
- Choisir la rubrique, puis **Chercher**. Le mot est ajouté à la rubrique. Google News français est interrogé tout de suite. Les articles trouvés arrivent dans la veille, rangés dans la rubrique choisie.
- Sous le résultat, les sites nouveaux cités par ces articles ont un bouton **Trouver le flux**. Il cherche le RSS du site et le propose dans l’onglet Radar.
- La croix d’une pastille retire le mot. Les articles déjà en base sont refiltrés aussitôt.

Le compteur affiché avant **Chercher** ne compte que ce qui est déjà en base.

### Vue 3D

Le bouton **3D** ouvre une fenêtre plein écran. Le nom de la veille est le groupe parent, au centre. Chaque rubrique, comme Général, est un groupe enfant, sur la même orbite que ses mots-clés. Tout tourne autour de ce nom. La taille d’un mot suit le nombre d’articles de la fenêtre en cours. La couleur relie un mot à sa rubrique.

- Glisser tourne la vue. La molette rapproche ou éloigne.
- **Rotation** relance ou coupe le mouvement automatique. Un glisser le coupe.
- Un clic sur un mot-clé ouvre à droite jusqu’à huit articles : titre, source, date et résumé. Le titre ouvre l’article dans un autre onglet.
- **Fermer** sur ce panneau, ou un clic dans le vide, le referme. Échap ou **Fermer** quitte la vue 3D.

Changer de veille ou de fenêtre pendant que la vue est ouverte recharge la scène.

### Radar

L’onglet **Radar** cherche de nouveaux flux pour la veille affichée. **Lancer le radar** :

1. retient jusqu’à six mots caractéristiques, un par rubrique quand c’est possible (un nom court comme MeshCore ou QGIS plutôt qu’une longue phrase) ;
2. interroge Google News en français, et aussi en anglais si le mot est en caractères latins sans accent ;
3. interroge le web avec ce mot accompagné de `rss` ou `feed` ;
4. reprend les éditeurs déjà vus dans les articles Google News, réseaux et recherches de la console ;
5. ouvre la page de chaque site nouveau et cherche un flux : lien RSS ou Atom, chemins habituels (`/feed`, `/rss.xml`), ou `releases.atom` pour un dépôt GitHub ;
6. ne propose le flux que si des titres récents, ou le titre du flux, correspondent aux mots de la veille.

Un site déjà connu, déjà proposé ou déjà écarté n’est pas reproposé. GitHub, GitLab, Codeberg, Medium, Substack, Blogspot et WordPress.com sont suivis dépôt par dépôt ou blog par blog, pas comme un seul domaine.

**Ajouter le flux** l’inscrit au catalogue commun et le lit une première fois. **Écarter** le mémorise pour ne plus le proposer. **Trouver le flux**, depuis l’onglet Mots, sonde le site demandé même si les titres ne collent pas encore : la proposition indique alors que le flux a été trouvé sans correspondance.

### Sources

L’onglet **Sources** liste le catalogue. Les erreurs de lecture sont en tête. Les services WMS y figurent pour mémoire : ils ne deviennent pas des articles.

### Créer une veille

En bas de la colonne de gauche, saisir un nom et **Créer**. Ajouter ensuite des mots dans Général, ou **Chercher** pour interroger Google News tout de suite. Au prochain **Rafraîchir les flux**, cette veille filtre le catalogue commun comme les autres, et ses mots entrent dans les recherches X, Instagram et Snap.

## Comment un article est retenu

Un article entre dans une veille si un mot-clé d’une de ses rubriques est trouvé dans le titre ou le résumé.

- Les accents sont ignorés.
- Un mot seul ne compte que comme mot entier : `radio` ne prend pas `radioamateur`.
- Une expression, ou un mot qui contient un trait d’union, est cherchée telle quelle.
- Dans une rubrique, les mots se combinent par OU.
- L’article est rangé dans la rubrique de plus haute priorité qui correspond.
- Si la source déclare déjà une rubrique de cette veille et que son filtre est `aucun`, cette rubrique est imposée. C’est le cas des recherches lancées avec **Chercher**.
- Les étiquettes de tendance s’affichent. Elles ne font pas entrer un article à elles seules.
- Aucun article daté d’avant le 1er janvier 2025 n’est montré.
- Une recherche lancée avec **Chercher** reste visible dans la fenêtre choisie même si Google News renvoie une date plus ancienne, tant que l’article vient d’être récupéré.

| Type de source | Comportement |
| --- | --- |
| Flux RSS ou Atom | Lu à chaque rafraîchissement. Avec `mots_cles`, seules les veilles dont un mot correspond gardent l’article |
| Google News du catalogue | Une recherche égale un flux. Le filtre d’origine est conservé |
| Recherche lancée par **Chercher** | Flux Google News de la veille ouverte, filtre `aucun`, rangé dans la rubrique choisie |
| X, Instagram, Snap | Recherches Google News régénérées à chaque rafraîchissement |
| Flux ajouté par le radar | `mots_cles`, visible par toutes les veilles, chacune filtrant avec ses mots |
| WMS | Enregistré, non téléchargé comme un fil d’articles |

Détail : [docs/sources.md](docs/sources.md) et [docs/comprendre.md](docs/comprendre.md).

## X, Instagram et Snap

À chaque **Rafraîchir les flux**, les mots-clés des rubriques sont cherchés via Google News :

- X sur `x.com` et `twitter.com`
- Instagram sur `instagram.com`
- Snap sur `snapchat.com`

Chaque réseau est interrogé en français et en anglais, par paquets d’au plus huit mots. Les sources générées portent un identifiant `rsoc-…`. Elles sont désactivées puis réécrites à chaque passe, pour suivre les mots ajoutés ou retirés. Un mot de moins de trois caractères n’est pas envoyé.

Les articles trouvés n’entrent dans une veille que si un de ses mots-clés correspond, comme pour les autres flux. Les recherches X déjà présentes dans le catalogue d’origine (LinkedIn, Mastodon, Bluesky, Threads, et les requêtes X importées) restent en plus.

Snap et Instagram n’exposent pas un flux des publications. Seules les pages reprises par Google News remontent.

## Publier

Sous le titre de la veille ouverte :

| Bouton | Effet |
| --- | --- |
| PDF, HTML, MD | Dépose ce format pour la veille ouverte, sur la fenêtre affichée |
| Toutes les veilles | Dépose les trois formats de chaque veille, chacune avec sa fenêtre enregistrée |

La barre du haut suit la fabrication, puis le dépôt. Un lien vers le fichier et un lien vers la page [Veille 2](https://f4eed.pages-perso.free.fr/Veille_2/) s’affichent à la fin. Le dépôt de toutes les veilles peut durer plusieurs minutes : un fichier est fabriqué par veille et par format, puis tout part dans la même session FTP, avec `index.html`. Une erreur sur un fichier n’arrête pas le reste.

`index.html` liste les veilles déposées, avec un lien PDF, un lien pour lire dans le navigateur, et un lien Markdown.

Les noms stables sont `Veille_IOT`, `Veille_Crise`, `Veille_Radio`, `Veille_Outils_PC`, `Veille_Blackout`, `Veille_Geomatique` et `Veille_Mesh`, chacun en `.pdf`, `.html` et `.md`. Une veille créée dans la console reçoit un nom du même genre, tiré de son titre.

`data\publications.json` mémorise, sur le poste, le dernier nom déposé pour chaque veille. Il sert à réécrire la page d’accueil au dépôt suivant.

Le Markdown a un sommaire, une section par rubrique, et pour chaque article la source, la date, les mots, un extrait et le lien. Le HTML reprend les mêmes articles, y compris pour un écran étroit. Le PDF est un rapport A4 : titre, périmètre, nombre d’articles, fenêtre et date, sommaire, puis une carte par article. Georgia pour les titres, Calibri pour le texte.

L’onglet **Courriel** choisit, pour chaque adresse, les veilles à envoyer. **Envoyer** expédie le message tout de suite, avec les liens vers les fichiers des Pages Perso et quelques titres. La boîte SMTP reste celle de la veille d’origine. Le courriel automatique du matin, lui, reste programmé dans `C:\Apps\veille_techno`. Détail : [docs/publication.md](docs/publication.md).

Le catalogue comprend aussi le flux du Haut Comité Français pour la Résilience Nationale, https://www.hcfrn.org/ (`blog-feed.xml`). Il est lu comme les autres flux : chaque veille n’en garde que les articles qui correspondent à ses mots.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `lancer.bat` | Démarre la console sous Windows |
| `requirements.txt` | `feedparser` et `PyYAML` |
| `veille_v2/__main__.py` | Point d’entrée `python -m veille_v2` |
| `veille_v2/__init__.py` | Ajoute `.vendor` de la veille d’origine au chemin Python |
| `veille_v2/serveur.py` | Pages et API sur le port 8770 |
| `veille_v2/collecte.py` | Téléchargement parallèle des flux |
| `veille_v2/filtre.py` | Filtre une veille sur les articles déjà en base, et prépare la vue 3D |
| `veille_v2/decouverte.py` | Recherche d’un mot et radar de nouveaux flux |
| `veille_v2/reseaux.py` | Recherches X, Instagram et Snap |
| `veille_v2/export.py` | PDF, HTML, Markdown et dépôt FTP |
| `veille_v2/courriel.py` | Envoi des veilles, adresse par adresse |
| `veille_v2/magasin.py` | Base SQLite |
| `veille_v2/seed.py` | Import unique du catalogue de la veille d’origine |
| `veille_v2/texte.py` | Normalisation des textes et des mots |
| `web/` | Interface : `index.html`, `app.js`, `style.css` |
| `data/veille.sqlite` | Articles, veilles, mots-clés, sources. Non versionnée |
| `data/publications.json` | Derniers fichiers déposés sur les Pages Perso |
| `docs/` | Installation, fonctionnement, usage, veilles, sources, publication |

L’interface est relue sur le disque à chaque chargement de page. Un changement de Python (`veille_v2\`) demande de relancer le processus. Un changement de `web\` ou de `docs\` est visible au rechargement du navigateur.

## Documentation

- [Installer et lancer](docs/installation.md)
- [Comprendre le fonctionnement](docs/comprendre.md)
- [Utiliser la console](docs/utilisation.md)
- [Les veilles](docs/profils.md)
- [Sources, mots-clés et radar](docs/sources.md)
- [Publier en PDF, HTML et Markdown](docs/publication.md)

Licence : [GNU GPL v3](LICENSE).
