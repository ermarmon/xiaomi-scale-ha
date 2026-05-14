# Changelog y documentación de cambios — v0.4.0

## Fixes de compatibilidad aplicados

### Fix 1 — paho-mqtt v2 API
`publish.single()` y `publish.multiple()` eliminados. Sustituidos por un cliente persistente
`mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)` creado una vez al arranque. El cliente incluye
un callback `on_disconnect` con reintentos exponenciales (máximo 3, backoff 1→2→4 s).
La estructura de topics `miscale/{USER_NAME}/weight` y el flag `retain` se mantienen intactos.

### Fix 2 — Timestamp UTC correcto
`datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')` reemplazado por
`datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')`.
El valor anterior no era timezone-aware y producía timestamps incorrectos si el host no estaba en UTC.

### Fix 3 — bleak>=0.21 compatibility
`BleakScanner(callback, device=...)` migrado a `BleakScanner(detection_callback=callback, device=...)`.
UUID keys en `service_data` verificados en formato lowercase completo (`0000181b-...`, `0000181d-...`),
que es el formato normalizado por bleak>=0.21.

### Fix 4 — requirements.txt
```
bleak>=0.21,<1.0
paho-mqtt>=2.0,<3.0
python-dateutil>=2.8
```

---

## Sistema multi-usuario por historial adaptativo

### Cómo funciona

El módulo `src/user_history.py` mantiene un `UserHistoryManager` que persiste mediciones
en `data/user_history.json` (creado en runtime, no incluido en el repo).

**Etapa 1 — Matching por historial (principal)**
Para cada usuario con ≥3 mediciones registradas, calcula la media de sus últimas 10
mediciones y comprueba si el peso entrante está dentro de ±2 kg de esa media.

- **1 candidato** → asignación directa, publica en `miscale/{NAME}/weight`, añade al historial.
- **0 candidatos** → fallback GT/LT (comportamiento original).
- **≥2 candidatos** → medición ambigua → publica en `miscale/pending` y dispara notificaciones.

**Etapa 2 — Fallback GT/LT (bootstrap y red de seguridad)**
Para usuarios con <3 mediciones en historial, se usa el rango `GT`/`LT` de `options.json`
como criterio de asignación. Así los usuarios nuevos acumulan historial hasta que la
etapa 1 toma el relevo.

### Campos nuevos en options.json (todos opcionales)

```json
{
  "NOTIFY_ALEXA": true,
  "ALEXA_MEDIA_TOPIC": "media_player/alexa_salon",
  "NOTIFY_MOBILE": true,
  "MOBILE_NOTIFY_TOPIC": "homeassistant/mobile_notify/pending_weight"
}
```

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `NOTIFY_ALEXA` | bool | `false` | Activa notificación Alexa Media Player en medición ambigua |
| `ALEXA_MEDIA_TOPIC` | str | `""` | Topic MQTT para Alexa Media Player (keatontaylor actionable) |
| `NOTIFY_MOBILE` | bool | `false` | Activa notificación HA companion app en medición ambigua |
| `MOBILE_NOTIFY_TOPIC` | str | `""` | Topic MQTT para HA mobile_app companion |

### Payload de medición pendiente (`miscale/pending`, retain=false)

```json
{
  "weight": 72.5,
  "unit": "kg",
  "timestamp": "2026-05-14T10:30:00+00:00",
  "candidates": ["Ernesto", "Otro"],
  "impedance": 512.0
}
```

### El script NO gestiona la asignación final

El script solo publica en `miscale/pending` y retorna. La respuesta del usuario
(a través de la notificación) la gestiona una automation de Home Assistant vía MQTT trigger.

### Ejemplo de automation HA para asignación

```yaml
alias: Mi Scale — pending assignment
mode: queued
trigger:
  - platform: mqtt
    topic: mobile_app/tu_movil/notify/action
condition: []
action:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.payload_json.action == 'ASSIGN_ERNESTO' }}"
        sequence:
          - service: mqtt.publish
            data:
              topic: miscale/Ernesto/weight
              payload: "{{ states('input_text.last_pending_payload') }}"
      - conditions:
          - condition: template
            value_template: "{{ trigger.payload_json.action == 'ASSIGN_DISCARD' }}"
        sequence:
          - service: logbook.log
            data:
              name: Mi Scale
              message: Pesaje descartado por el usuario.
```

---

## Deuda técnica (fuera de scope, no tocar)

- `os.system('clear')` al nivel de módulo: limpia el terminal en cada import, inofensivo pero sorprendente en tests.
- Los bloques `except: pass` en el BLE callback suprimen silenciosamente todos los errores de parsing; un `logging.debug` ayudaría a diagnosticar variantes de firmware.
- `_build_payload` construye JSON por concatenación de strings; reemplazarlo con `json.dumps` sería más seguro.
- `OLD_MEASURE` es global y se resetea en cada reinicio del proceso, por lo que la primera lectura tras reinicio siempre se publica aunque sea duplicada.
- El original leía `json.load(json_file)["options"]` (key hardcodeada). Corregido a `raw.get("options", raw)` para compatibilidad con el Supervisor de HA moderno que escribe sin wrapper.
