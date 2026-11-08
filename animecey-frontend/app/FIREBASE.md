# Notifications Firebase (FCM) — Magi-Stream

Les notifications arrivent en quelques secondes, application fermée. Sans Firebase, l'app vérifie le serveur
toutes les ~15 min (`MagiNotifyWorker`) : ce système reste actif en secours et ne crée pas de doublon.

## 1. Firebase (une fois)
1. https://console.firebase.google.com → **Ajouter un projet**.
2. **Ajouter une application Android**, nom du package : `online.magistream.app` (pas besoin de SHA-1).
3. Télécharge **google-services.json**.
4. GitHub → Settings → Secrets and variables → Actions → **New repository secret**
   - nom : `GOOGLE_SERVICES_JSON`, valeur : tout le contenu du fichier.
   (ou mets le fichier dans `app/google-services.json` du dépôt)
5. Console Firebase → ⚙ Paramètres du projet → **Comptes de service** → **Générer une nouvelle clé privée**.
   Ce JSON va sur ton hébergeur (Koyeb/Railway) dans la variable `FIREBASE_CREDENTIALS_JSON`. Ne le mets jamais dans GitHub.

## 2. Serveur (à adapter à ton backend)
L'app envoie son token à `POST {API}/push/fcm` avec `{"token": "...", "platform": "android"}`.
Quand une notification est créée, envoie un message **data-only** (sans bloc `notification`), priorité haute :

```python
# pip install firebase-admin
import json, os
from datetime import timedelta
import firebase_admin
from firebase_admin import credentials, messaging

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(json.loads(os.environ["FIREBASE_CREDENTIALS_JSON"])))

def send_app_notification(n, tokens: list[str]) -> list[str]:
    """Envoie à tous les tokens. Renvoie ceux qui ne sont plus valides (à supprimer en base)."""
    data = {  # mêmes champs que /app-notifications ; toutes les valeurs doivent être des chaînes
        "id": str(n.id), "title": n.title, "body": n.body or "",
        "path": n.path or "/",            # "/anime/12" ou un lien https://...
        "image_url": n.image_url or "",
    }
    dead = []
    for i in range(0, len(tokens), 500):
        batch = tokens[i:i + 500]
        res = messaging.send_each_for_multicast(messaging.MulticastMessage(
            data=data, tokens=batch,
            android=messaging.AndroidConfig(priority="high", ttl=timedelta(hours=24)),
        ))
        for tok, r in zip(batch, res.responses):
            if not r.success and isinstance(r.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                dead.append(tok)
    return dead
```

Route d'enregistrement (exemple FastAPI, à adapter à ta base) :

```python
@router.post("/push/fcm")
def register_fcm(body: FcmIn, db: Session = Depends(get_db)):   # FcmIn : token: str, platform: str = "android"
    if not db.query(FcmToken).filter_by(token=body.token).first():
        db.add(FcmToken(token=body.token)); db.commit()
    return {"ok": True}
```
Appelle `send_app_notification` en tâche de fond (`BackgroundTasks`) juste après avoir enregistré la notification du bot.

## 3. Vérifier
Reconstruis l'APK, installe-le, ouvre-le une fois (le token est envoyé), ferme-le complètement, puis envoie une notification.
Le message « Firebase activé » doit apparaître dans les logs du workflow GitHub.
