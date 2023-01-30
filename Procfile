release: python manage.py migrate
web: gunicorn mysite.wsgi
worker: python manage.py rqworker high default low 