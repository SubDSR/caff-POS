web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn pos_system.wsgi:application --bind 0.0.0.0:$PORT
