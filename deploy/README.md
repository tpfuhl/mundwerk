# Mundwerk — Deployment (Apache + mod_wsgi)

Gleiches Muster wie arbeitsstunden.proportiodivina.eu: Apache-VHost,
mod_wsgi-Daemon, Let's Encrypt. Annahme: Repo unter `/home/thomas/mundwerk`.

## Einmalige Einrichtung auf dem Server

```bash
# 1. DNS: A-Record für mundwerk.proportiodivina.eu auf die Server-IP

# 2. Code + Umgebung
# Das Repo ist privat (github.com/tpfuhl/mundwerk) — der Server braucht
# einen Deploy-Key: auf dem Server einmalig
#   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519   # falls kein Key da
# und den Inhalt von ~/.ssh/id_ed25519.pub auf GitHub eintragen
# (Repo → Settings → Deploy keys, read-only genügt), oder vom Laptop aus:
#   gh repo deploy-key add <pubkey-datei> --title cloudserver
cd /home/thomas
git clone git@github.com:tpfuhl/mundwerk.git mundwerk
cd mundwerk/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Produktionskonfiguration (.env liegt neben manage.py, ist gitignored)
cat > .env <<EOF
DJANGO_SECRET_KEY=$(.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
DJANGO_DEBUG=0
EOF
chmod 600 .env

# 4. Datenbank, Static-Dateien, Admin-User
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser

# 5. Zertifikat (Apache muss auf Port 80 für die Challenge erreichbar sein)
sudo certbot certonly --apache -d mundwerk.proportiodivina.eu

# 6. VHost aktivieren
sudo cp /home/thomas/mundwerk/deploy/apache-mundwerk.conf /etc/apache2/sites-available/mundwerk.conf
sudo a2ensite mundwerk
sudo apachectl configtest && sudo systemctl reload apache2

# 7. Smoke-Test
curl https://mundwerk.proportiodivina.eu/api/items/
```

## Updates einspielen

```bash
cd /home/thomas/mundwerk && git pull
server/.venv/bin/pip install -r server/requirements.txt
server/.venv/bin/python server/manage.py migrate
server/.venv/bin/python server/manage.py collectstatic --noinput
touch server/config/wsgi.py     # WSGIScriptReloading lädt den Daemon neu
```

## MFA (Forced Alignment) einrichten

Einmalig auf dem Server (als thomas; ~3 GB unter ~/miniforge3):

```bash
curl -sL -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash miniforge.sh -b -p ~/miniforge3 && rm miniforge.sh
~/miniforge3/bin/conda create -n mfa -c conda-forge montreal-forced-aligner -y
export PATH=~/miniforge3/envs/mfa/bin:$PATH
mfa model download acoustic german_mfa
mfa model download dictionary german_mfa
echo "MFA_BIN=/home/thomas/miniforge3/envs/mfa/bin/mfa" >> ~/mundwerk/server/.env
touch ~/mundwerk/server/config/wsgi.py
```

Der erste Alignment-Lauf baut den Lexikon-Cache (~30 s), danach ~8 s pro
Aufnahme. Ohne `MFA_BIN` in der `.env` läuft die Analyse weiter mit der
Auto-Segmentierung (Fallback).

## Stolpersteine

- **`WSGIApplicationGroup %{GLOBAL}` nicht entfernen** — parselmouth und
  numpy laufen nicht in mod_wsgi-Subinterpretern (Absturz beim ersten
  API-Call wäre die Folge).
- **Kein `/media/`-Alias**: Aufnahmen sind personenbezogene Daten und
  werden nicht öffentlich ausgeliefert.
- **Schreibrechte**: der mod_wsgi-Daemon läuft als www-data, muss aber in
  `server/media/` schreiben (Uploads) und `server/db.sqlite3` (+ das
  Verzeichnis darüber) beschreiben können:
  `chgrp -R www-data server/media server/db.sqlite3 && chmod -R g+w …`
  Alternativ `user=thomas group=thomas` im WSGIDaemonProcess ergänzen
  (wie in der auskommentierten Zeile der arbeitsstunden-Config).
- **Token-Auth**: alle Endpoints verlangen `Authorization: Token <key>`.
  Neue Tokens (z. B. für Kirsten/Tester): auf dem Server
  `manage.py drf_create_token <username>` (User vorher im Admin anlegen)
  und beim Tester in `local.properties` als `mundwerk.apiToken=…`
  eintragen. Voraussetzung im VHost: `WSGIPassAuthorization On` —
  sonst verwirft Apache den Header und alles ist 401.
- Android-App: `BASE_URL` in `MundwerkApi.kt` auf
  `https://mundwerk.proportiodivina.eu/` stellen (https → der
  Cleartext-Eintrag in network_security_config.xml wird nicht gebraucht).
- MFA (Forced Alignment) ist noch nicht integriert — wenn es so weit ist,
  kommen Celery + Redis dazu und die Analyse wird asynchron.
