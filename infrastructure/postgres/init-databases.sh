#!/bin/sh
set -e

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
	echo "Multiple database creation requested: $POSTGRES_MULTIPLE_DATABASES"
	for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
		echo "  Creating database '$db'"
		psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" -c "CREATE DATABASE $db;" || true
		psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" -c "GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;" || true
	done
	echo "Multiple databases created successfully."
fi
