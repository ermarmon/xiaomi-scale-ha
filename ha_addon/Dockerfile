ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=0.4.2
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest

ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache \
    python3 \
    py3-pip \
    gcc \
    musl-dev \
    glib-dev \
    bluez \
    dbus

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY src/ ./src/
COPY run.sh .
RUN chmod +x run.sh

CMD ["/app/run.sh"]
