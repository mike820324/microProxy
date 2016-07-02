test:
	@PYTHONPATH=. python microproxy/test/run_tests.py

lint:
	@flake8 && echo "Static Check Without Error"

coverage:
	@PYTHONPATH=. coverage run --source microproxy microproxy/test/run_tests.py
