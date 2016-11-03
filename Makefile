test:
	python -m unittest discover

lint:
	@flake8 && echo "Static Check Without Error"

coverage:
	@coverage run --source=microproxy -m unittest discover

install:
	pip install -U --no-deps --process-dependency-links .

install-all:
	pip install -U --process-dependency-links .
	pip install -U .[viewer]
	pip install -U .[develop]
