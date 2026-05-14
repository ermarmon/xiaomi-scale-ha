#!/usr/bin/env bashio

bashio::log.info "Starting Xiaomi Mi Scale add-on v0.4.0..."

# Map HA options to /data/options.json which Xiaomi_Scale.py reads directly.
# The HA Supervisor writes all configured options to /data/options.json automatically.
# No manual env-var export needed — the script reads the file at startup.

# Ensure history data directory exists and is writable
mkdir -p /data/user_history_data

# Symlink data dir so user_history.py writes to persistent /data volume
if [ ! -L /app/data ]; then
    ln -sf /data/user_history_data /app/data
fi

bashio::log.info "Launching Xiaomi_Scale.py..."
exec python3 -u /app/src/Xiaomi_Scale.py
