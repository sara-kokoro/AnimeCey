/**
 * Application Android de Magi-Stream.
 * L'APK est construit par GitHub Actions (.github/workflows/build-apk.yml) et publié avec un lien stable :
 *   https://github.com/<ton-compte>/<ton-dépôt>/releases/download/apk-latest/magi-stream.apk
 * Mets ce lien dans la variable d'environnement VITE_APP_APK_URL (ou remplace la valeur par défaut ci-dessous).
 * Par défaut, le bouton pointe vers /magi-stream.apk (fichier à déposer dans le dossier public/).
 */
export const APP = {
  apkUrl:
    (import.meta.env.VITE_APP_APK_URL as string | undefined) ??
    "https://github.com/sara-kokoro/AnimeCey/releases/download/apk-latest/magi-stream.apk",
  /** Page de la dernière version : sa description contient « build N » (voir le workflow GitHub). */
  releaseApi:
    (import.meta.env.VITE_APP_RELEASE_API as string | undefined) ??
    "https://api.github.com/repos/sara-kokoro/AnimeCey/releases/tags/apk-latest",
};
