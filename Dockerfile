FROM python:alpine

COPY docker/motd /etc/motd
COPY docker/profile /root/profile
ENV ENV=/root/profile

WORKDIR /usr/src/cilium

COPY dist/microscope.pyz microscope

CMD [ "./microscope" ]
