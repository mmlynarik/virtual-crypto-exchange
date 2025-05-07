.PHONY: runprod, rmprod

runprod:
	docker-compose -f docker-compose-prod.yaml up

rmprod:
	docker-compose -f docker-compose-prod.yaml rm --force
