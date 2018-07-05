FROM python:alpine

RUN apk update
RUN apk add make
WORKDIR /usr/src/microscope
COPY . .
RUN make pyz

FROM python:alpine

COPY docker/motd /etc/motd
COPY docker/profile /root/profile
ENV ENV=/root/profile

RUN apk --no-cache add --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing moreutils

COPY --from=0 /usr/src/microscope/pyz/microscope.pyz /bin/microscope
RUN ln -s /bin/microscope /bin/cilium-microscope

WORKDIR /usr/src/microscope

CMD [ "microscope" ]
