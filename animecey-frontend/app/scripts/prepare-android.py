#!/usr/bin/env python3
"""Prépare le projet Android généré par `npx cap add android` (lancé depuis le dossier app/).

  1. copie le plugin natif (téléchargements en arrière-plan) et MainActivity ;
  2. ajoute les permissions et le service dans AndroidManifest.xml ;
  3. remplace l'icône par celle du site ;
  4. règle le numéro de version (argument : numéro de build).
"""
import pathlib
import re
import shutil
import subprocess
import sys

build = sys.argv[1] if len(sys.argv) > 1 else "1"
root = pathlib.Path(__file__).resolve().parent.parent
android = root / "android"
java_dir = android / "app/src/main/java/online/magistream/app"
manifest = android / "app/src/main/AndroidManifest.xml"
res = android / "app/src/main/res"
gradle = android / "app/build.gradle"

# 1. Code natif
java_dir.mkdir(parents=True, exist_ok=True)
for f in (root / "native").glob("*.java"):
    shutil.copy(f, java_dir / f.name)

# 2. Manifeste
xml = manifest.read_text(encoding="utf-8")
perms = [
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    "android.permission.WAKE_LOCK",
]
add = "".join(f'    <uses-permission android:name="{p}" />\n' for p in perms if p not in xml)
xml = xml.replace("<application", add + "    <application", 1) if add else xml
if "DownloadService" not in xml:
    service = '        <service android:name=".DownloadService" android:exported="false" android:foregroundServiceType="dataSync" />\n    '
    xml = xml.replace("</application>", service + "</application>", 1)
manifest.write_text(xml, encoding="utf-8")

# 3. Icône (anciennes icônes carrées sur toutes les versions d'Android)
icon = root.parent / "public/icon-512.png"
if icon.exists():
    shutil.rmtree(res / "mipmap-anydpi-v26", ignore_errors=True)
    sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for dens, px in sizes.items():
        d = res / f"mipmap-{dens}"
        d.mkdir(parents=True, exist_ok=True)
        for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
            subprocess.run(["convert", str(icon), "-resize", f"{px}x{px}", str(d / name)], check=True)

# 4. Version
g = gradle.read_text(encoding="utf-8")
g = re.sub(r"versionCode\s+\d+", f"versionCode {int(build)}", g, count=1)
g = re.sub(r'versionName\s+"[^"]*"', f'versionName "1.0.{int(build)}"', g, count=1)
gradle.write_text(g, encoding="utf-8")
print("Projet Android prêt.")
