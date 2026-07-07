# Mundwerk — Deployment (Apache + mod_wsgi)

Gleiches Muster wie arbeitsstunden.proportiodivina.eu: Apache-VHost,
mod_wsgi-Daemon, Let's Encrypt. Annahme: Repo unter `/home/thomas/mundwerk`.

## Einmalige Einrichtung auf dem Server

```bash
# 1. DNS: A-Record für mundwerk.proportiodivina.eu auf die Server-IP

# 2. Code + Umgebung
cd /home/thomas
git clone <repo-url> mundwerk
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
- **API ist noch offen** (AllowAny): jeder kann Audio hochladen. Für den
  Anfang tolerierbar, aber Token-Auth sollte der nächste Schritt nach dem
  Deployment sein — spätestens bevor die App an Tester geht.
- Android-App: `BASE_URL` in `MundwerkApi.kt` auf
  `https://mundwerk.proportiodivina.eu/` stellen (https → der
  Cleartext-Eintrag in network_security_config.xml wird nicht gebraucht).
- MFA (Forced Alignment) ist noch nicht integriert — wenn es so weit ist,
  kommen Celery + Redis dazu und die Analyse wird asynchron.
