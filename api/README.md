# Virtual Crypto Exchange (VCE) Backend

## 1. Install virtual environment
This project uses `uv` package manager. To properly install virtual environment, uv executable needs to be present in the system. If it's not, you can download and install it using curl:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After cloning the repository, the virtual environment can be set up using the command:
```
uv sync
```

## 2. Environment files
Secrets are not committed. Docker compose reads them from env files in the repository root, which the `just` commands pass via `--env-file`:

- `.env.dev` (used by `just rundev`): `JWT_SECRET_KEY`, `GITHUB_CLIENT_SECRET`
- `.env.prod` (used by `just runprod`): `JWT_SECRET_KEY`, `GITHUB_CLIENT_SECRET`, `BACKEND_DB_PASSWORD`

`JWT_SECRET_KEY` can be generated with `openssl rand -base64 32`.

For running migrations from the host (`just migrate`), `api/.env` holds the database connection: `BACKEND_DB_HOST`, `BACKEND_DB_NAME`, `BACKEND_DB_USER`, `BACKEND_DB_PASSWORD`. The dev database is published on `localhost:5433`.

## 3. Run the FastAPI app in development mode using docker-compose
The API application can be run using just command which will spin up three docker containers - python app, postgres database and nextjs server
```
just rundev
```

Rebuild the images after changing dependencies (`pyproject.toml`, `uv.lock`):
```
just rundev --build
```

The `api/vce` source directory is mounted into the container, so code changes are picked up by the auto-reload without a rebuild. Database migrations are applied automatically on every container start (`vce-migrate`).

## 4. Docker images
The API has two Dockerfiles, both built with `api` as the build context:

| File | Used by | Contents | Command |
|---|---|---|---|
| `Dockerfile.dev` | `docker-compose-dev.yaml` | app + dev dependencies | `fastapi dev --reload` |
| `Dockerfile.prod` | GitHub Actions (`build-api.yml`) | app dependencies only | `fastapi run` |

Both are multi-stage builds: dependencies are installed with `uv` in the `ghcr.io/astral-sh/uv` builder image and the resulting `/app` (source + `.venv`) is copied into a slim `python` runtime image. No additional system packages are installed, and the app runs as the non-root `vce` user on port 8000.

The production image is built and pushed to Docker Hub as `miromlynarik/vce-api:prod` on every push to `master` touching `api/`. Watchtower on the server pulls the new image and restarts the container. To build it locally:
```
docker build -f api/Dockerfile.prod -t vce-api:prod api
```

## 5. Just commands
| Command | Description |
|---|---|
| `just` | List all available commands |
| `just rundev [args]` | Start the dev stack (db, api, web) in the foreground, e.g. `just rundev --build` |
| `just runprod [args]` | Start the prod stack (db, api, web, caddy, watchtower) in the foreground |
| `just migrate` | Apply alembic migrations to the local db using `api/.env` |
| `just prune` | Prune the docker build cache |

## 6. API docs and usage:
API docs can be found at
```
http://127.0.0.1:8000/docs
```
