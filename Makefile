freeze:
	pip3 freeze | grep -Ev "pkg-resources|twine|osm-humanized-opening-hours|mccabe|pycodestyle|pyflakes|flake8|requests|idna|pkginfo|tqdm|urllib3|chardet|certifi" > requirements.txt

freeze-dev:
	pip3 freeze | grep -Ev "pkg-resources|osm-humanized-opening-hours" > requirements-dev.txt

tests:
	python3 tests.py

flake8:
	python3 -m flake8 humanized_opening_hours

benchmark-simple:
	@echo "=== Time for a single field:"
	@python3 -m timeit -v -r 5 -u sec -n 1 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Mo-Fr 08:00-19:00")'
	@echo "=== Time for 10 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 10 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Mo-Fr 08:00-19:00")'
	@echo "=== Time for 100 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 100 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Mo-Fr 08:00-19:00")'
	@echo "=== Time for 1000 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 1000 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Mo-Fr 08:00-19:00")'

benchmark-complex:
	@echo "=== Time for a single field:"
	@python3 -m timeit -v -r 5 -u sec -n 1 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Jan-Feb Mo-Fr 08:00-19:00")'
	@echo "=== Time for 10 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 10 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Jan-Feb Mo-Fr 08:00-19:00")'
	@echo "=== Time for 100 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 100 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Jan-Feb Mo-Fr 08:00-19:00")'
	@echo "=== Time for 1000 fields:"
	@python3 -m timeit -v -r 5 -u sec -n 1000 -s 'import humanized_opening_hours as hoh' 'oh = hoh.OHParser("Jan-Feb Mo-Fr 08:00-19:00")'

coverage:
	@coverage erase
	coverage run tests.py
	@clear
	coverage report -m

help:
	@echo "Available commands:"
	@echo "  freeze          Updates 'requirements.txt'"
	@echo "  freeze-dev      Updates 'requirements-dev.txt'"
	@echo "  tests           Runs unit tests"
	@echo "  flake8          Runs flake8 tests"
	@echo "  benchmark       Runs benchmark for 1, 10, 100 and 1000 fields"
