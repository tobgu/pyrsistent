clear-dist:
	rm dist/*

sdist:
	python setup.py sdist

pypi: clear-dist sdist
	twine upload dist/*
