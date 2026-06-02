# Xiaomi Scale HA

[![GitHub Release](https://img.shields.io/github/v/release/ermarmon/xiaomi-scale-ha?style=flat-square)](https://github.com/ermarmon/xiaomi-scale-ha/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat-square)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

Custom Home Assistant integration for **Xiaomi Mi Body Composition Scales**. Uses the native Home Assistant Bluetooth stack — no MQTT broker, no add-on, no Docker. Works with ESP32 BT proxies.

---

## Features

- Auto-detects weight measurements via Bluetooth (BLE passive scan)
- Assigns measurements to users by weight range (GT/LT)
- Calculates body metrics: BMI, body fat, water, bone mass, muscle mass, visceral fat, metabolic age, basal metabolism, protein
- Sends mobile notifications on assignment, with actionable buttons to resolve ambiguous readings
- Optional Alexa actionable notifications
- Full measurement history per user
- Diagnostic sensor with last BLE event and last notification result
- Compatible with **ESP32 Bluetooth proxies** (no Bluetooth adapter needed on the HA host)

---

## Supported Scales

| Model | Name |
|---|---|
| XMTZCO1HM / XMTZC04HM | Mi Smart Scale 2 |
| XMTZC02HM | Mi Body Composition Scale |
| XMTZC05HM | Mi Body Composition Scale 2 |

Scales that broadcast on BLE service UUID `0000181b` (v2, with impedance) or `0000181d` (v1, weight only) are supported.

---

## Requirements

- Home Assistant 2023.6 or newer
- Bluetooth integration enabled (built-in) — or at least one **ESP32 Bluetooth proxy** reachable from HA
- The scale's MAC address (find it in the Xiaomi Health app under device settings)

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations
2. Click the three-dot menu (⋮) → **Custom repositories**
3. Paste `https://github.com/ermarmon/xiaomi-scale-ha` and select category **Integration**
4. Click **Add**, then find **Xiaomi Scale HA** in the list and install it
5. Restart Home Assistant

### Manual

1. Download or clone this repository
2. Copy the `custom_components/xiaomi_scale_ha` folder into your HA `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

After installation, go to **Settings → Devices & Services → Add Integration** and search for **Xiaomi Scale HA**.

### Step 1 — Basic setup

| Field | Description |
|---|---|
| Name | Friendly name for this scale device |
| MAC Address | BLE MAC address of the scale (e.g. `AA:BB:CC:DD:EE:FF`) |
| Users (JSON) | List of users — see format below |

### Step 2 — Options (editable after setup)

| Option | Default | Description |
|---|---|---|
| Persistent notification on ambiguous reading | On | Creates a HA notification when the weight matches multiple users |
| Notify on assigned measurement | Off | Sends a mobile push when a reading is successfully assigned |
| Impedance wait (seconds) | 8 | Seconds to wait for an impedance reading before finalising |
| Alexa actionable notifications | Off | Send Alexa Yes/No prompts for ambiguous readings |

---

## User configuration (JSON)

Each user is an object in the `USERS` JSON list:

```json
[
  {
    "NAME": "Alice",
    "GT": 55,
    "LT": 75,
    "SEX": "female",
    "HEIGHT": 165,
    "DOB": "1990-06-15",
    "NOTIFY_SERVICE": "notify.mobile_app_alice_phone",
    "ALEXA_DEVICE": ""
  },
  {
    "NAME": "Bob",
    "GT": 75,
    "LT": 100,
    "SEX": "male",
    "HEIGHT": 180,
    "DOB": "1985-03-22",
    "NOTIFY_SERVICE": "notify.mobile_app_bob_phone",
    "ALEXA_DEVICE": "media_player.echo_bathroom"
  }
]
```

| Field | Required | Description |
|---|---|---|
| `NAME` | Yes | Display name — also used as entity label |
| `GT` | Yes | Weight greater than this (lower bound, same unit as scale) |
| `LT` | Yes | Weight less than this (upper bound, same unit as scale) |
| `SEX` | Yes | `male` or `female` — used for body metric calculations |
| `HEIGHT` | Yes | Height in cm |
| `DOB` | Yes | Date of birth in `YYYY-MM-DD` format |
| `NOTIFY_SERVICE` | No | HA notify service for this user (e.g. `notify.mobile_app_xyz`) |
| `ALEXA_DEVICE` | No | `media_player` entity ID of the Alexa device to query |

> Weight ranges must not overlap. If two users match the same weight the reading is held as **pending** until confirmed manually or via notification action.

---

## Entities

For each configured user the integration creates:

| Entity | Type | Description |
|---|---|---|
| `sensor.<name>_<user>_weight` | Sensor | Latest weight in kg. Attributes contain all metrics |

Plus per-device:

| Entity | Type | Description |
|---|---|---|
| `sensor.<name>_pending_measurement` | Sensor | Active when a reading is awaiting assignment. Attributes contain candidates and raw data |
| `sensor.<name>_last_ble_measurement` | Diagnostic | Last BLE event state and details. Includes `last_notification` result |
| `sensor.<name>_history` | Diagnostic | Total stored measurements. Attributes contain per-user history |

### Weight sensor attributes

`weight`, `unit`, `bmi`, `body_fat`, `water`, `bone_mass`, `muscle_mass`, `visceral_fat`, `basal_metabolism`, `lean_body_mass`, `protein`, `metabolic_age`, `impedance`, `timestamp`, `rssi`

---

## Services

| Service | Parameters | Description |
|---|---|---|
| `xiaomi_scale_ha.assign_pending` | `user_name` | Assign the pending reading to a user |
| `xiaomi_scale_ha.discard_pending` | — | Discard the pending reading |
| `xiaomi_scale_ha.send_pending_notification` | — | Re-send the pending notification |
| `xiaomi_scale_ha.clear_history` | `user_name` (optional) | Clear stored history for one or all users |
| `xiaomi_scale_ha.delete_history_measurement` | `user_name`, `index` | Delete a specific history entry |

---

## Notifications

### Mobile push — assigned reading

Enable **Notify on assigned measurement** in options and set `NOTIFY_SERVICE` per user. When a reading is assigned you receive:

> **Peso registrado**  
> Alice: 62.3 kg (BMI 22.9, grasa 24.1%)

### Mobile push — ambiguous reading

When a weight matches more than one user, each candidate's `NOTIFY_SERVICE` receives an actionable notification with buttons:

> **Pesaje sin asignar**  
> Pesaje sin asignar: 68.5 kg. Candidatos: Alice, Bob.  
> [Soy Alice] [Soy Bob] [Descartar]

Tapping a button fires a `mobile_app_notification_action` event which the integration handles automatically.

### Alexa actionable notifications

Enable **Alexa actionable notifications** in options and fill in `ALEXA_DEVICE` per user. Requires the [Alexa Media Player](https://github.com/custom-components/alexa_media_player) integration and a helper script that calls `alexa_media_player.play_media`.

---

## Diagnostic sensor

The `last BLE measurement` sensor (visible under **Diagnostic** in the device page) exposes the full state of the last processing cycle. Check its attributes after a weigh-in to understand exactly what happened.

| `state` value | Meaning |
|---|---|
| `listening` | Integration started, waiting for BLE advertisements |
| `not_stabilized` | Scale is still settling — reading in progress |
| `measurement_received` | Valid stabilised reading received |
| `assigned` | Reading matched exactly one user |
| `pending` | Reading matched multiple users, waiting for confirmation |
| `no_user_matched` | Weight outside all configured GT/LT ranges |
| `parse_error` | Could not parse the BLE advertisement |
| `unsupported_advertisement` | BLE packet from the scale MAC but not a scale payload |

The `last_notification` attribute shows the outcome of the last notification attempt:

| `result` value | Meaning |
|---|---|
| `sent` | Notification dispatched successfully |
| `skipped` | Not sent — see `reason` (`notify_assigned_disabled`, `no_notify_service`, `already_finalized`) |
| `error` | Service call failed — see `error` field |

---

## Troubleshooting

**No readings are received at all**
- Confirm the MAC address matches exactly (use the Xiaomi Health app → device info)
- Check that Bluetooth is working in HA: Settings → System → Hardware → Bluetooth
- Step on the scale and wait ~10 s, then reload the page — `last BLE measurement` state should change from `listening`

**Weight is received but not assigned to any user**
- State will be `no_user_matched`. Check that the measured weight (shown in attributes) falls within a user's `GT`/`LT` range and that units match the scale setting

**Notification not received after an assigned reading**
- Check `last_notification` in the diagnostic sensor attributes
- `notify_assigned_disabled` → enable the option in integration settings
- `no_notify_service` → add `NOTIFY_SERVICE` to the user JSON
- `already_finalized` → same-weight session was merged with a previous reading (step on scale twice with the same weight in <30 s)
- `error` → the notify service call failed; check the HA logs for details

**Logs**

Enable debug logging for detailed output:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.xiaomi_scale_ha: debug
```

---

## Credits

Body metric calculations adapted from the work of [@wiecosystem](https://github.com/wiecosystem/Bluetooth) and [@syssi](https://gist.github.com/syssi/4108a54877406dc231d95514e538bde9).

Original scale decoder based on [xiaomi_mi_scale](https://github.com/lolouk44/xiaomi_mi_scale) by [@lolouk44](https://github.com/lolouk44).

---

## License

MIT
