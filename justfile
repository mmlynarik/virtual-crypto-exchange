dev_compose := "--env-file .env.dev -f docker-compose-dev.yaml"
prod_compose := "--env-file .env.prod -f docker-compose-prod.yaml"


# Default command to list all available commands.
default:
    @just --list

# Start the dev stack (db, api, web) in the foreground; `just rundev --build` rebuilds images.
rundev *args:
    @echo "Starting dev containers..."
    @docker compose {{dev_compose}} up {{args}}

# Start the prod stack in the foreground.
runprod *args:
    @echo "Starting prod containers..."
    @docker compose {{prod_compose}} up {{args}}

# Apply alembic migrations to the local db.
migrate:
    @echo "Running migrations..."
    @cd api && uv run --env-file ../api/.env alembic upgrade head
