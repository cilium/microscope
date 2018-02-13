FROM python:alpine

COPY docker/motd /etc/motd
COPY docker/profile /root/profile
ENV ENV=/root/profile

COPY dist/microscope.pyz /bin/microscope

CMD [ "microscope" ]
