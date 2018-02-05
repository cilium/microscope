FROM python:alpine

WORKDIR /usr/src/cilium

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY microscope .

CMD [ "python", "./microscope.py" ]
