#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for database if needed (optional)
# if [ "$DATABASE" = "postgres" ]
# then
#     echo "Waiting for postgres..."
#     while ! nc -z $DB_HOST $DB_PORT; do
#       sleep 0.1
#     done
#     echo "PostgreSQL started"
# fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the main command
exec "$@"
