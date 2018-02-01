all:
	mkdir -p dist/monitor
	pip install -r requirements.txt -t dist/monitor
	cp monitor.py dist/monitor
	python -m zipapp dist/monitor -m "monitor:main"
	#add shebang
	echo '#!/usr/bin/env python' | cat - dist/monitor.pyz > dist/tmp
	mv dist/tmp dist/monitor.pyz
	chmod +x dist/monitor.pyz

clean:
	rm -rf dist
