# Publier en PDF, HTML et Markdown

Les rapports de la console sont déposés à part de ceux du matin.

| | Veille d’origine | Veille 2 |
| --- | --- | --- |
| Qui lance | `C:\Apps\veille_techno`, envoi vers 7 h | Les boutons de http://127.0.0.1:8770 |
| Dossier FTP | `veille` | `Veille_2` |
| Page | https://f4eed.pages-perso.free.fr/veille/ | https://f4eed.pages-perso.free.fr/Veille_2/ |
| Formats | PDF et HTML | PDF, HTML et Markdown |
| Courriel | Oui | Non |

Pages Perso affiche les fichiers. Elle n’exécute pas la collecte.

## Boutons

Sous le titre de la veille ouverte :

- **PDF**, **HTML** ou **MD** publie ce format, pour cette veille, sur la fenêtre affichée (1 à 90 jours).
- **Toutes les veilles** publie les trois formats de chaque veille. Chaque veille garde sa propre fenêtre, celle enregistrée à côté de son nom. Black-out part donc sur 14 jours si on n’a pas changé ce réglage, une veille réglée sur 3 jours part sur 3 jours.

La barre du haut suit la fabrication, puis le dépôt. Un lien vers le fichier et un lien vers la page Veille 2 s’affichent à la fin. Tant qu’un export ou une collecte tourne, les boutons sont indisponibles.

Le dépôt de toutes les veilles peut durer plusieurs minutes : un PDF est fabriqué par veille, puis tous les fichiers partent dans la même session FTP, avec `index.html`.

## Page publique

`index.html` liste les veilles déposées, avec un lien PDF, un lien pour lire dans le navigateur, et un lien Markdown. L’adresse est https://f4eed.pages-perso.free.fr/Veille_2/.

Les noms stables sont `Veille_IOT`, `Veille_Crise`, `Veille_Radio`, `Veille_Outils_PC`, `Veille_Blackout`, `Veille_Geomatique` et `Veille_Mesh`, chacun en `.pdf`, `.html` et `.md`. Une veille créée dans la console reçoit un nom du même genre, tiré de son titre.

`data\publications.json` mémorise, sur le poste, le dernier nom déposé pour chaque veille. Il sert à réécrire la page d’accueil au dépôt suivant.

## Présentation

Le Markdown a un sommaire, une section par rubrique, et pour chaque article la source, la date, les mots, un extrait et le lien.

Le PDF est un rapport A4 : titre de la veille, périmètre, nombre d’articles, fenêtre et date, sommaire, puis une carte par article. Il utilise Georgia pour les titres et Calibri pour le texte. Ces polices doivent être dans `C:\Windows\Fonts`.

Le HTML reprend les mêmes articles, pour une lecture dans le navigateur, y compris sur un écran étroit.

## Identifiants FTP

Ils ne sont pas recopiés dans Veille 2. Le programme lit :

- `C:\Apps\veille_techno\config\email.yaml`, bloc `publication` (`hote`, `utilisateur`)
- `C:\Apps\veille_techno\config\email.secrets.yaml`, clé `mot_de_passe`

Le serveur par défaut est `ftpperso.free.fr`. L’identifiant Free est le login Pages Perso, sans `@`. Le dossier distant est fixé à `Veille_2`. S’il n’existe pas, il est créé au premier dépôt.

Changer un destinataire ou couper le courriel du matin se fait dans la veille d’origine, pas ici. Voir `C:\Apps\veille_techno\docs\paramétrage.md`.
