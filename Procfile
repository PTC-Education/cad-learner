release: python manage.py migrate
web: gunicorn mysite.wsgi
worker: python mysite/manage.py rqworker high default low 