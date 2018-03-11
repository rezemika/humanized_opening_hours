freeze:
	pip3 freeze | grep -Ev "pkg-resources|twine|osm-humanized-opening-hours|mccabe|pycodestyle|pyflakes|flake8" > requirements.txt

freeze-dev:
	pip3 freeze | grep -Ev "pkg-resources|osm-humanized-opening-hours" > requirements-dev.txt

tests:
	python3 humanized_opening_hours/tests.py

flake8:
	python3 -m flake8 humanized_opening_hours

help:
	@echo "Available commands:"
	@echo "  freeze          Updates 'requirements.txt'"
	@echo "  tests           Runs unit tests"
	@echo "  flake8          Runs flake8 tests"
