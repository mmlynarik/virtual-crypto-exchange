.PHONY: runprod rmprod db api ui

rundev:
	docker-compose -f docker-compose-dev.yaml up

runprod:
	docker-compose -f docker-compose-prod.yaml up

rmprod:
	docker-compose -f docker-compose-prod.yaml rm --force

fe:
	cd web && npm run dev

db:
	docker run -d --name postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -p 5433:5432 -v postgres_data:/var/lib/postgresql/data postgres:15

be:
	cd api && fastapi dev --host "0.0.0.0" --port 8001 --reload src/vce/app.py
