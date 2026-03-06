web: gunicorn superrecord.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 2 --worker-class gthread --worker-tmp-dir /dev/shm --timeout 120 --log-file - --access-logfile - --error-logfile -
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py setup_initial_data
