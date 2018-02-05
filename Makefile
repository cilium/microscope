distpath = dist/microscope
pyzpath = dist/microscope.pyz

all:
	mkdir -p $distpath
	pip install -r requirements.txt -t $(distpath)
	cp -r microscope $(distpath)
	python -m zipapp $(distpath) -m "microscope.microscope:main"
	#add shebang
	echo '#!/usr/bin/env python' | cat - $(pyzpath) > dist/tmp
	mv dist/tmp $(pyzpath)
	chmod +x $(pyzpath)

clean:
	rm -rf dist

docker:
	docker build -t cilium/monitor-mux .
