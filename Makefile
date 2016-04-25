test:
	@PYTHONPATH=. python tests/run_tests.py

lint:
	@flake8 && echo "Static Check Without Error"

