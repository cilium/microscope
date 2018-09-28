FROM python:3.7.0-alpine3.8

RUN apk update
RUN apk add make libffi-dev build-base libressl-dev
WORKDIR /usr/src/microscope
COPY . .
RUN make pyz

FROM python:3.7.0-alpine3.8

COPY docker/motd /etc/motd
COPY docker/profile /root/profile
ENV ENV=/root/profile

COPY --from=0 /usr/src/microscope/pyz/microscope.pyz /bin/microscope
RUN ln -s /bin/microscope /bin/cilium-microscope

WORKDIR /usr/src/microscope

CMD [ "microscope" ]
