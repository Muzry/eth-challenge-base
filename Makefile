dev:
	cd example && brownie compile
	DEBUG_MODE=True uvicorn server:app --reload

dev-sui:
	uvicorn server:app --reload

protoc:
	docker build --target protoc -t protoc --platform linux/amd64 .
	docker run --name protoc protoc
	docker cp protoc:/protobuf-builder/protobuf eth_challenge_base && docker rm protoc

lint:
	mypy .
	black --check . --diff
	flake8 --ignore=E501,W503 --show-source
	isort --profile black . --check --diff

format:
	black .
	isort --profile black .
