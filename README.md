# StockPass

Inventory and Transport Management WebAPP for businesses.

---

# Run venv

.\.venv\Scripts\activate

# Run the Development Server with HTTPS

uvicorn StockPass.asgi:application --host  0.0.0.0  --port  8000 --reload

# db migration

python manage.py makemigrations
python manage.py migrate

python manage.py makemigrations && python manage.py migrate

# celery worker

celery -A portal worker --loglevel=info --pool=solo

# celery beat

celery -A portal beat --loglevel=info

# shell

python manage.py shell

# delete py cache

Get-ChildItem -Recurse -Force -Directory -Filter "**pycache**" | Remove-Item -Recurse -Force

# build

python -m build

## AUTO SEQUENCE UPD

python manage.py shell --interface=python -c "from django.apps import apps; print(' '.join(a.label for a in apps.get_app_configs()))"

# add extra settings

from aiki_core.extra_settings import EXTRA_MIDDLEWARE, EXTRA_REST_FRAMEWORK
