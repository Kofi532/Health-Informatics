# PythonAnywhere Deployment Guide

## 1. Clone and set up environment

```bash
git clone https://github.com/Kofi532/Health-Informatics.git
cd Health-Informatics
python3.10 -m venv ~/.virtualenvs/healthenv
source ~/.virtualenvs/healthenv/bin/activate
pip install -r requirements.txt
```

## 2. Configure environment variables

On PythonAnywhere, set these environment variables for your web app:

- `DJANGO_SECRET_KEY` = a long random secret
- `DEBUG` = `False`
- `ALLOWED_HOSTS` = `yourusername.pythonanywhere.com`
- `CSRF_TRUSTED_ORIGINS` = `https://yourusername.pythonanywhere.com`

You can define variables in your WSGI file (or use PythonAnywhere startup scripts), for example:

```python
import os
os.environ['DJANGO_SECRET_KEY'] = 'replace-with-a-long-random-secret'
os.environ['DEBUG'] = 'False'
os.environ['ALLOWED_HOSTS'] = 'yourusername.pythonanywhere.com'
os.environ['CSRF_TRUSTED_ORIGINS'] = 'https://yourusername.pythonanywhere.com'
```

## 3. Prepare database and static files

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 4. Configure PythonAnywhere Web app

- Create a new web app: Manual configuration, Python 3.10+
- Source code: `/home/yourusername/Health-Informatics`
- Virtualenv: `/home/yourusername/.virtualenvs/healthenv`
- WSGI file: set Django settings module to `health_informatics.settings`
- Static files mapping:
  - URL: `/static/`
  - Directory: `/home/yourusername/Health-Informatics/staticfiles`

## 5. WSGI file template

Use PythonAnywhere's generated WSGI file and keep only one Django block like this:

```python
import os
import sys

path = '/home/yourusername/Health-Informatics'
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_informatics.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

## 6. Reload and verify

- Click **Reload** in the PythonAnywhere Web tab
- Visit `https://yourusername.pythonanywhere.com`
- Open `/admin` and log in with your superuser

## 7. Replace old records with local simulated data

After pulling latest code on PythonAnywhere, clear old records and load the shared simulated dataset:

```bash
python manage.py migrate
python manage.py flush --noinput
python manage.py loaddata patients/fixtures/simulated_data.json
python manage.py collectstatic --noinput
```

Then reload the web app from the PythonAnywhere **Web** tab.

## Notes

- Do not upload local `.venv` or `venv`
- SQLite works for starter deployment; PostgreSQL is recommended for growth
- If you update dependencies later: `pip install -r requirements.txt` and reload
