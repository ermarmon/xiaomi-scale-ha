FROM python:3.11-slim

RUN apt-get update && apt-get install --no-install-recommends -y \
    bluetooth \
    bluez \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY ha_addon/run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
