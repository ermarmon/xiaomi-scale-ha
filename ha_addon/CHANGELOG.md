# Changelog

## [0.4.1] - 2026-05-14

### Fixed
- Packaging del add-on autocontenido: `ha_addon/` incluye `src/` y `requirements.txt`.
- Compatibilidad con Supervisor/Home Assistant 2026.04+: base image declarada en `Dockerfile`
  y build sin depender de `build_from`.
- Dockerfile migrado a paquetes Alpine (`apk`) para las imagenes base de Home Assistant.
- Permisos de Bluetooth/D-Bus declarados en `config.yaml` (`host_dbus`, `usb`,
  `NET_ADMIN`, `NET_RAW`).

## [0.4.0] — 2026-05-14

### Fixed
- **paho-mqtt v1 → v2 API**: reemplazado `publish.single()` por cliente persistente
  `mqtt.Client(CallbackAPIVersion.VERSION2)` con reconexión automática (backoff exponencial, max 3 reintentos).
- **UTC timestamp**: corregido `datetime.now()` (no timezone-aware) por
  `datetime.now(timezone.utc)` — los timestamps ahora son correctos independientemente
  del timezone del host.
- **bleak >=0.21**: migrado `BleakScanner(callback, ...)` a
  `BleakScanner(detection_callback=callback, ...)`. UUID keys verificadas en formato
  lowercase completo para compatibilidad con bleak>=0.21.
- **Dependencias**: fijadas con rangos explícitos
  (`bleak>=0.21,<1.0`, `paho-mqtt>=2.0,<3.0`, `python-dateutil>=2.8`).
- **options.json key**: compatible con Supervisor moderno (escribe sin wrapper `"options"`)
  y formato legacy (con wrapper).

### Added
- **Sistema multi-usuario por historial adaptativo**: reemplaza la asignación por rangos
  fijos (GT/LT). Para usuarios con ≥3 mediciones, usa la media de las últimas 10 como
  referencia (tolerancia ±2 kg). Los usuarios nuevos usan GT/LT como bootstrap hasta
  acumular historial suficiente.
- **Medición ambigua → `miscale/pending`**: cuando 2+ usuarios son candidatos, publica
  el payload en `miscale/pending` (retain=false) con peso, unidad, timestamp, candidatos
  e impedancia.
- **Notificaciones accionables Alexa Media Player** (opcional): publica en
  `ALEXA_MEDIA_TOPIC` con formato compatible con keatontaylor actionable notifications.
- **Notificaciones accionables HA mobile companion app** (opcional): publica en
  `MOBILE_NOTIFY_TOPIC` con acciones `ASSIGN_{NAME}` y `ASSIGN_DISCARD`.
- **Packaging como HA local add-on**: carpeta `ha_addon/` con `config.json`,
  `Dockerfile`, `run.sh` y este `CHANGELOG.md`. Listo para copiar a `addons/` de HA.

## [0.3.5] — 2022-10-xx (upstream lolouk44/xiaomi_mi_scale)

Última versión oficial del repo original. Ver historial upstream para detalles.
