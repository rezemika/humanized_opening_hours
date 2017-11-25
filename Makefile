freeze:
	pip3 freeze | grep -v "pkg-resources" | grep -v "twine" > requirements.txt

tests:
	python3 humanized_opening_hours/tests.py
