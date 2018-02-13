FROM python:alpine

RUN apk update
RUN apk add make
WORKDIR /usr/src/microscope
COPY . .
RUN make dist

FROM python:alpine

COPY docker/motd /etc/motd
COPY docker/profile /root/profile
ENV ENV=/root/profile

COPY --from=0 /usr/src/microscope/dist/microscope.pyz /bin/microscope

CMD [ "microscope" ]
