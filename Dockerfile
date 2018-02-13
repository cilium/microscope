FROM python:alpine

WORKDIR /usr/src/cilium

COPY dist/microscope.pyz microscope

CMD [ "./microscope" ]
