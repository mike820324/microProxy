test:
	@PYTHONPATH=. python tests/run_tests.py

lint:
	@flake8 && echo "Static Check Without Error"

coverage:
	@PYTHONPATH=. coverage run --source microproxy tests/run_tests.py
