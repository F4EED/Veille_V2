# Installer et lancer

Veille 2 tourne sur le poste, pas sur les Pages Perso. Le site public ne fait qu’afficher les fichiers déjà déposés.

## Ce qu’il faut

- Windows
- Python 3, lancé par `py -3` ou `python`
- Le dossier `C:\Apps\veille_techno`, pour le premier import du catalogue et pour le mot de passe FTP déjà utilisé par la veille d’origine
- Les polices Georgia et Calibri, présentes dans `C:\Windows\Fonts`, pour les PDF

Les bibliothèques sont `feedparser` et `PyYAML`, listées dans `requirements.txt`.

Si `C:\Apps\veille_techno\.vendor` existe, Veille 2 l’ajoute à son chemin Python et n’a pas besoin d’une seconde installation. Sinon :

```bat
py -3 -m pip install -r requirements.txt
```

à lancer dans `C:\Apps\Veille_V2`.

## Premier lancement

```bat
lancer.bat
```

ou :

```bat
cd /d C:\Apps\Veille_V2
py -3 -m veille_v2
```

Au premier démarrage, le programme copie dans `data\veille.sqlite` :

- les sept veilles et leurs mots-clés (`config\keywords*.yaml`)
- les flux RSS, les recherches Google News et les réseaux du catalogue
- les services WMS, enregistrés mais non lus comme des articles

Cet import n’a lieu qu’une fois. Le modifier les YAML ensuite ne change pas la console. Les mots-clés se règlent dans l’interface, et restent dans la base.

La console affiche `Veille vive : http://127.0.0.1:8770`. Ouvrir cette adresse.

## Depuis le portail

Sur http://127.0.0.1:8080/, choisir **Veille (V2)**.

Si rien n’écoute encore sur le port 8770, **Ouvrir** lance `python -m veille_v2` dans `C:\Apps\Veille_V2`, puis ouvre la console. Si la console tourne déjà, le lien s’ouvre directement.

## Arrêter

Fermer la fenêtre de commande qui a lancé `lancer.bat`, ou quitter le processus Python qui écoute sur le port 8770. La base `data\veille.sqlite` reste sur le disque.

## Fichiers locaux

| Fichier | Rôle |
| --- | --- |
| `data\veille.sqlite` | Base de la console. Non versionnée |
| `data\publications.json` | Liste des derniers PDF, HTML et Markdown déposés |

Le mot de passe FTP n’est pas dans ce dossier. La publication le lit dans `C:\Apps\veille_techno\config\email.secrets.yaml`, clé `mot_de_passe`, comme la veille d’origine. Le serveur et l’identifiant viennent de `config\email.yaml`, bloc `publication`.
