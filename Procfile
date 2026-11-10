release: python manage.py migrate
web: gunicorn mysite.wsgi --max-requests 500 --max-requests-jitter 50
worker: python manage.py rqworker high default low 