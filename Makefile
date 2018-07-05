distpath = pyz/microscope
pyzpath = pyz/microscope.pyz

pyz:
	mkdir -p $(distpath)
	pip install -r requirements.txt -t $(distpath)
	cp -r microscope/ $(distpath)
	cp microscope/__main__.py $(distpath)/__main__.py
	python -m zipapp $(distpath)
	#add shebang
	echo '#!/usr/bin/env python' | cat - $(pyzpath) > pyz/tmp
	mv pyz/tmp $(pyzpath)
	chmod +x $(pyzpath)

clean:
	rm -rf pyz
	rm -rf dist

docker-image:
	docker build -t cilium/microscope .

docker-ci:
	docker build -t cilium/microscope:ci ci

install:
	python setup.py install

dist:
	python setup.py sdist

upload: dist
	twine upload dist/*
