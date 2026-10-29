# Application Android Magi-Stream

L'application est un conteneur Android (Capacitor) qui charge https://www.magi-stream.online : le site
reste mis à jour comme d'habitude, sans republier l'APK. Elle ajoute :

- des téléchargements en arrière-plan (notification de progression, bouton « Annuler », reprise) ;
- le stockage des épisodes dans le téléphone ;
- une page « Hors connexion » qui liste les épisodes téléchargés (`www/offline.html`).

## Obtenir l'APK
1. Dépose ce projet dans ton dépôt GitHub (le dossier `.github/workflows/` à la racine).
2. GitHub → onglet **Actions** → « Construire l'APK Android » → **Run workflow**.
3. Après ~5-10 minutes, l'APK est publié avec un lien stable :
   `https://github.com/<compte>/<dépôt>/releases/download/apk-latest/magi-stream.apk`
4. Mets ce lien dans la variable `VITE_APP_APK_URL` de ton hébergeur : le bouton « Télécharger notre application » l'utilisera.

## Fichiers
- `capacitor.config.json` : adresse du site, page hors connexion.
- `native/` : plugin et service de téléchargement (Java), copiés dans le projet Android par `scripts/prepare-android.py`.
- `debug.keystore` : clé de signature fixe, pour que les mises à jour s'installent par-dessus l'ancienne version.
  Elle est publique : suffisant pour distribuer l'APK toi-même, pas pour le Play Store.
