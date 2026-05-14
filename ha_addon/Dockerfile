ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=0.4.1
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-python:3.12

ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache \
    bluez \
    dbus \
    glib

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
