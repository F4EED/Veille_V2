# Comprendre le fonctionnement

Veille 2 sépare la collecte et la lecture.

1. **Rafraîchir les flux** télécharge les sources une fois, en parallèle, et enregistre les articles dans `data\veille.sqlite`.
2. Chaque veille filtre cette base tout de suite. Ajouter un mot, en retirer un, ou changer la fenêtre ne retélécharge rien.

La veille d’origine enchaîne sept collectes. Ici, une collecte sert toutes les veilles, y compris celles créées ensuite dans la console.

## Ce qu’une veille retient

Un article entre dans une veille si un mot-clé d’une de ses rubriques est trouvé dans le titre ou le résumé.

- Les accents sont ignorés.
- Un mot seul ne compte que comme mot entier : `radio` ne prend pas `radioamateur`.
- Une expression, ou un mot qui contient un trait d’union, est cherchée telle quelle.
- L’article est rangé dans la rubrique de plus haute priorité qui correspond.
- Si la source déclare déjà une rubrique de cette veille et que son filtre est `aucun`, cette rubrique est imposée. C’est le cas des recherches Google News lancées depuis la console.

Les étiquettes de tendance s’affichent, mais ne font pas entrer un article à elles seules.

Aucun article daté d’avant le 1er janvier 2025 n’est montré. Une recherche lancée avec **Chercher** reste visible dans la fenêtre choisie même si Google News renvoie une date plus ancienne, tant que l’article vient d’être récupéré.

## Fenêtre

Chaque veille a sa propre fenêtre : 1, 3, 7, 14, 30 ou 90 jours. Black-out est importée à 14 jours, les six autres à 7. Changer la fenêtre ne fait que réafficher la base.

## Sources

Le catalogue importé mélange :

- des flux RSS et Atom, gardés seulement s’ils matchent les mots de la veille (`filtre: mots_cles`)
- des recherches Google News déjà ciblées, reprises plus largement quand elles sont marquées `filtre: aucun`
- des requêtes de réseaux sociaux
- des services WMS, présents dans la base pour mémoire, pas transformés en articles

Un flux ajouté par le radar est en `mots_cles` : toutes les veilles peuvent le lire, chacune ne garde que ce qui la concerne.

## Radar

Le radar ne se contente pas des sites déjà cités dans les articles lus. Pour la veille affichée, il retient quelques mots caractéristiques des rubriques (un nom comme MeshCore ou Meshtastic plutôt qu’une longue phrase), puis :

- interroge Google News en français, et aussi en anglais si le mot est en caractères latins sans accent
- interroge le web avec ce mot et `rss` ou `feed`
- reprend les éditeurs déjà vus dans les articles Google News, réseaux et recherches de la console

Il ouvre ensuite la page de chaque site nouveau, cherche un flux (lien RSS de la page, chemins habituels, ou `releases.atom` pour un dépôt GitHub) et ne propose le flux que si des titres récents correspondent aux mots de la veille. Un site déjà connu, déjà ajouté ou déjà écarté n’est pas reproposé. GitHub, GitLab et les plateformes du même genre sont suivis dépôt par dépôt, pas comme un seul site.

## Publication

Les boutons PDF, HTML et MD fabriquent le rapport de la veille affichée, sur sa fenêtre actuelle, et le déposent par FTP dans le dossier `Veille_2`. **Toutes les veilles** fait les trois formats pour chaque veille, avec la fenêtre enregistrée de chacune, puis réécrit la page d’accueil.

Le courriel du matin n’est pas envoyé par cette console. Il reste programmé dans `C:\Apps\veille_techno`, vers https://f4eed.pages-perso.free.fr/veille/.

## Ce qui reste sur le poste

Pages Perso affiche les fichiers. La collecte, le filtre, le radar et la fabrication des PDF s’exécutent ici. Fermer le navigateur n’arrête pas la console : il faut quitter le programme qui écoute sur le port 8770.
