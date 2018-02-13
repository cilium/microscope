distpath = dist/microscope
pyzpath = dist/microscope.pyz

dist:
	mkdir -p $(distpath)
	pip install -r requirements.txt -t $(distpath)
	cp -r microscope/ $(distpath)
	cp microscope/__main__.py $(distpath)/__main__.py
	python -m zipapp $(distpath)
	#add shebang
	echo '#!/usr/bin/env python' | cat - $(pyzpath) > dist/tmp
	mv dist/tmp $(pyzpath)
	chmod +x $(pyzpath)

clean:
	rm -rf dist

docker: dist
	docker build -t cilium/microscope .

install:
	python setup.py install
