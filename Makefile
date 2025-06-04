.PHONY: runprod rmprod db api ui

rundev:
	docker-compose -f docker-compose-dev.yaml up

runprod:
	docker-compose -f docker-compose-prod.yaml up

rmprod:
	docker-compose -f docker-compose-prod.yaml rm --force --stop

fe:
	cd web && npm run dev

db:
	docker run -d --name postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -v postgres_data:/var/lib/postgresql/data postgres:15

be:
	cd api && fastapi dev --host "0.0.0.0" --port 8000 --reload src/vce/app.py

rmc:
	docker rm -vf $$(docker ps -aq)

rmi:
	docker rmi -f $$(docker images -aq)
