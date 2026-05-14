FROM python:3.11-alpine

RUN apk add --no-cache \
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
